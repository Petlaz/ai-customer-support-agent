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
| OpenAI no billing credits | RAG retrieval uses mock (random) embeddings | Add credits at `platform.openai.com/settings/billing` — pipeline auto-switches to real embeddings |
| Anthropic no billing credits | Non-blocking | Only needed if switching `LLM_PROVIDER=anthropic` |
| GitHub Actions CI exit code 4 | All CI runs failing | Fixed: removed `addopts` from pyproject.toml; pytest was applying addopts before `--override-ini` could clear them |

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



