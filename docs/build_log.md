# Build Log

Concise record of what worked, what did not work, and key decisions per phase.

---

## Phase 0 — Environment & Dependencies [DONE]
**2026-06-21**

**What worked:**
- Python 3.11.13 venv, 33 packages installed, `.env` configured
- Langfuse connection verified (US region: `https://us.cloud.langfuse.com`)
- All imports from `config/settings.py` and `config/constants.py` pass

**What did not work:**
- OpenAI API calls — key set but no billing credits (429 quota error)
- Anthropic API calls — key set but no billing credits (400 insufficient_quota)

**Decisions / Notes:**
- WARNING: OpenAI key accidentally written into `.env.example` — caught, reverted with `git restore`, keys rotated
- Langfuse must use US region endpoint, not the default EU one

---

## Phase 3b — Core Data Models [DONE]
**2026-06-22**

**What worked:**
- All 6 Pydantic schemas in `api/schemas/` import cleanly
- `AgentState` TypedDict in `agents/state.py` imports cleanly
- SQLAlchemy engine connects to SQLite at `data/support_agent.db`
- Alembic migration `74ea40ee529d` generated and applied — 8 tables confirmed

**What did not work:**
- Nothing failed in this phase

**Decisions / Notes:**
- Alembic `env.py` reads `DATABASE_URL` from `config/settings.py` at runtime — no hardcoded URLs in config files
- All models must be imported in `alembic/env.py` for autogenerate to detect them
- Inserted Phase 3b — original checklist placed database models at Phase 11, which would have broken the Memory Layer (Phase 6)

---

## Phase 4 — Sample Data [DONE]
**2026-06-23**

**What worked:**
- 4 policy documents written with realistic content (Nexus Software — fictional SaaS)
- 18 sample tickets covering all 6 categories validated
- 3 customer histories and 6 historical resolutions with full agent responses written
- 10 eval cases validated — 3 designed to force escalation (>$500 refund, GDPR, fraud keywords)
- All JSON files parse without errors: 18 + 3 + 6 + 10 records

**What did not work:**
- Nothing failed in this phase

**Decisions / Notes:**
- `technical_support_guide.md` was missing from the checklist but referenced in `config/constants.py` — added and ticked
- Escalation triggers in eval cases: EVAL-006 (high-value refund), EVAL-007 (GDPR Article 17), EVAL-008 (fraud + lawyer keywords)

---

## Phase 5 — RAG Layer [DONE]
**2026-06-24**

**What worked:**
- `rag/document_loader.py` — loaded 4 policy docs with source + category metadata
- `rag/text_extractor.py` — strips markdown headings, bold, links, code, tables
- `rag/chunker.py` — split 4 docs into 50 chunks (CHUNK_SIZE=500, CHUNK_OVERLAP=50)
- `rag/embeddings.py` — mock fallback active; same text always produces the same vector (deterministic hash-based)
- `rag/vector_store.py` — ChromaDB upsert/query/delete working; 50 chunks stored and queried
- `rag/retriever.py` — policy retrieval and similar-ticket retrieval both functional
- `rag/metadata_filter.py` — filter by source file and ticket category works
- `rag/context_formatter.py` — formats retrieved chunks with source labels for LLM prompt
- Full pipeline test passed: load -> chunk -> embed -> store -> query -> format

**What did not work:**
- Semantic relevance is not meaningful — mock embeddings return random vectors so retrieved chunks are random, not related to the query. This is expected and correct behaviour until OpenAI credits are active.

**Decisions / Notes:**
- `rag/embeddings.py` tries OpenAI first on every call and falls back to mock on `RateLimitError` — no config flag needed; swap is automatic when credits are loaded
- ChromaDB metadata only accepts str/int/float/bool — list fields (categories) are stored as comma-separated strings and parsed back on retrieval
- `delete_collection` is now a no-op if collection does not exist (fix applied during testing)

---

## Phase 6 — Memory Layer [DONE]
**2026-06-24**

**What worked:**
- `memory/short_term_memory.py` — AgentState accessor/builder helpers; partial state dicts for LangGraph nodes
- `memory/long_term_memory.py` — `get_or_create_customer`, `save_ticket` (idempotent on ticket_id), `get_customer_tickets`, `update_ticket_classification`
- `memory/semantic_memory.py` — `index_ticket`, `index_tickets_batch`, `retrieve_similar`; wraps Phase 5 ChromaDB TICKETS_COLLECTION
- `memory/conversation_history.py` — LangChain HumanMessage/AIMessage builders, `format_history`, `save_messages_to_db`
- `memory/customer_history.py` — `CustomerHistory` schema with prior ticket list, escalation count, refund count from DB
- `memory/ticket_memory.py` — `update_ticket_outcome` (sets status to "escalated" when required), `log_agent_decision`, `save_escalation`
- `memory/memory_retriever.py` — unified read entry point returning `MemoryContext` (customer history + similar cases)
- `memory/memory_manager.py` — `load_memory()` + `save_memory()` as clean interface for agent nodes
- `tests/test_memory.py` — 48 tests, 48 passed; in-memory SQLite + EphemeralChromaDB, no external services
- Smoke test: `load_memory(db, ticket)` → `MemoryContext` with 1 ticket, 0 similar cases (empty tickets collection) ✓

**What did not work:**
- ChromaDB `EphemeralClient` shares in-process state across tests (singleton pattern) — two tests failed because prior test left data in `TICKETS_COLLECTION`. Fixed by calling `delete_collection(TICKETS_COLLECTION)` at the start of affected tests
- `index_tickets_batch` generated duplicate IDs (`doc_0`) when documents had no `source` field — fixed by using `ticket_id` as the `source` field before calling `add_documents`

**Decisions / Notes:**
- Distance → similarity conversion: `score = 1 / (1 + distance)` — range [0, 1], no additional normalisation needed
- `save_memory` is safe to call even if the graph did not complete all nodes — missing state fields default to empty values
- `historical_tickets` ChromaDB collection is empty until `semantic_memory.index_tickets_batch()` is run (Phase 12 Airflow DAG will automate this)

---

## Blocking Issues

| Issue | Impact | Action |
|-------|--------|--------|
| OpenAI no billing credits | RAG retrieval uses mock (random) embeddings; LLM nodes fall back to keyword classifier / template responses | Add credits at `platform.openai.com/settings/billing` — pipeline auto-switches to real embeddings and real LLM calls |
| Anthropic no billing credits | Non-blocking | Only needed if switching `LLM_PROVIDER=anthropic` |
| GitHub Actions CI exit code 4 | All CI runs failing | Fixed: removed `addopts` from pyproject.toml; pytest was applying addopts before `--override-ini` could clear them |
| ChromaDB shared in-process state (full test suite) | `test_retrieve_similar_tickets_empty_collection_returns_empty` fails when test_memory.py runs first | Known issue; test passes in isolation; fix is to add `delete_collection(TICKETS_COLLECTION)` before the assertion in test_retrieval.py |

---

## Phase 7 — LangGraph Agent Workflow [DONE]
**2026-06-25**

**What worked:**
- `agents/confidence.py` — `check_escalation_keywords`, `meets_threshold`, `should_escalate`; keyword scan is case-insensitive, covers all 14 ESCALATION_KEYWORDS constants
- `agents/prompts.py` — `CLASSIFICATION_PROMPT`, `DRAFT_RESPONSE_PROMPT`, `SUMMARIZE_PROMPT` as ChatPromptTemplate instances
- `agents/nodes/receive_ticket.py` — initialises all AgentState fields to defaults; appends HumanMessage to messages list
- `agents/nodes/retrieve_long_term_memory.py` — calls `customer_history.get_customer_history(db, customer_id)` with isolated SessionLocal; serialises CustomerHistory to list[dict]
- `agents/nodes/retrieve_semantic_memory.py` — calls `semantic_memory.retrieve_similar(query)` with distance→similarity conversion; graceful empty-list fallback
- `agents/nodes/classify_ticket.py` — `ChatOpenAI.with_structured_output(ClassificationOutput)` for structured JSON; keyword-based fallback classifier (confidence=0.0) when LLM unavailable
- `agents/nodes/retrieve_policy.py` — `retrieve_policy_chunks(query)` + `format_context`; graceful empty-list fallback
- `agents/nodes/draft_response.py` — `ChatOpenAI` with `DRAFT_RESPONSE_PROMPT`; fallback to static template when LLM unavailable
- `agents/nodes/check_confidence.py` — conditional edge function; returns `"route"` or `"escalate"` based on `should_escalate(state)`
- `agents/nodes/route_ticket.py` — `CATEGORY_TO_DEPARTMENT` lookup; defaults to `CUSTOMER_SUCCESS_TEAM` for unknown categories
- `agents/nodes/escalate_ticket.py` — routes to `HUMAN_REVIEW_QUEUE`; escalation_reason describes whether keyword or low-confidence triggered
- `agents/nodes/summarize_ticket.py` — `ChatOpenAI` with `SUMMARIZE_PROMPT`; fallback to formatted template string
- `agents/nodes/store_memory.py` — calls `update_ticket_outcome`, `log_agent_decision`, `save_escalation` (conditional); isolated SessionLocal per invocation
- `agents/nodes/log_decision.py` — lazy `from langfuse import Langfuse` (inside function); creates trace + 4 spans; no-op if keys not configured
- `agents/graph.py` — `StateGraph(AgentState)` with 11 nodes, `add_conditional_edges` at `draft_response` → `check_confidence_node` → `route_ticket` | `escalate_ticket` → `summarize_ticket` → `store_memory` → `log_decision` → END
- `tests/test_agent_graph.py` — 57 tests, all passed; full graph integration tests (routing + escalation + LLM-unavailable paths)

**What did not work:**
- `str(Department.BILLING_TEAM)` returns `"Department.BILLING_TEAM"` (Enum repr), not `"Billing Team"` — fixed by using `.value` everywhere
- `@patch("agents.nodes.log_decision.Langfuse")` fails because Langfuse is a lazy import (not a module attribute) — fixed by patching `"langfuse.Langfuse"` instead
- LangChain pipe `PROMPT | MagicMock` wraps plain MagicMock in `RunnableLambda` (calls `mock(input)` not `mock.invoke(input)`) — fixed by setting both `mock.return_value` and `mock.invoke.return_value`

**Decisions / Notes:**
- LLM nodes (classify, draft, summarize) all have graceful fallbacks so the graph never crashes even with no OpenAI credits
- `classify_ticket` fallback uses keyword-based classifier that returns `confidence=0.0`, which automatically triggers escalation via `check_confidence`
- DB sessions are isolated per node (new SessionLocal per call) — acceptable for SQLite dev; production should use FastAPI dependency injection via `RunnableConfig`
- Langfuse trace spans are created for: classify_ticket, retrieve_policy, draft_response, route_or_escalate


---

## Upcoming

| Phase | Goal | Needs OpenAI? |
|-------|------|--------------|
| Phase 7 | LangGraph agent graph — classify, retrieve, draft, route, escalate | Yes (LLM calls) |
| Phase 8 | Agent tools — classify_ticket, retrieve_policy, check_escalation | Yes |
| Phase 9 | Human-in-the-loop — escalation queue, human review | No |
| Phase 6 | Memory layer — short-term, long-term, semantic | No |
| Phase 7 | LangGraph agent graph | Yes |
| Phase 8 | Agent tools | Yes |



