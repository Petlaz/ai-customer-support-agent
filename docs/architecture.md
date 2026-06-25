# System Architecture

## Overview

The AI Customer Support Automation Agent is a stateful, multi-step AI system built with LangGraph. It receives a customer support ticket, classifies it, retrieves relevant policy knowledge and customer history, drafts a response, decides whether to route or escalate, and persists every decision for audit and evaluation.

---

## High-Level Architecture

```
Customer / API Client
        │
        ▼
┌───────────────────┐
│  FastAPI Backend  │  POST /tickets/analyze
│  (Phase 10)       │
└────────┬──────────┘
         │  TicketInput
         ▼
┌────────────────────────────────────────────────────────────┐
│                  LangGraph Agent Graph                      │
│                                                            │
│  receive_ticket                                            │
│       │                                                    │
│       ├──► retrieve_long_term_memory  ──► SQLite           │
│       ├──► retrieve_semantic_memory  ──► ChromaDB          │
│       │                                                    │
│  classify_ticket  ──► OpenAI gpt-4o-mini                  │
│       │                                                    │
│  retrieve_policy  ──► ChromaDB (policy_documents)         │
│       │                                                    │
│  draft_response   ──► OpenAI gpt-4o-mini                  │
│       │                                                    │
│  check_confidence ──► confidence score vs threshold        │
│       │                                                    │
│       ├── score ≥ 0.75 ──► route_ticket                   │
│       │                        │                           │
│       └── score < 0.75 ──► escalate_ticket                │
│                                │                           │
│  summarize_ticket  ◄───────────┘                           │
│       │                                                    │
│  store_memory  ──► SQLite + ChromaDB                      │
│       │                                                    │
│  log_decision  ──► Langfuse                               │
│                                                            │
└────────────────────────────────────────────────────────────┘
         │
         ▼  TicketResponse (classification, response,
              routing_decision, escalated, confidence_score,
              summary, langfuse_trace_url, tokens_used, cost_usd)
```

---

## Component Map

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Agent Graph** | LangGraph ≥ 0.2 | Stateful multi-step workflow with conditional routing |
| **LLM — Primary** | OpenAI gpt-4o-mini | Classification + response drafting |
| **LLM — Fallback** | Anthropic claude-3-5-sonnet | Alternative provider when OpenAI unavailable |
| **Embeddings** | text-embedding-3-small (1536d) | Policy chunk + ticket semantic vectors |
| **Vector Store** | ChromaDB ≥ 0.5 | Stores policy chunks and historical ticket embeddings |
| **Relational DB** | SQLite (dev) / PostgreSQL (prod) | Customers, tickets, agent logs, escalations, conversations |
| **Migrations** | Alembic ≥ 1.13 | Schema versioning; migration `74ea40ee529d` applied |
| **Observability** | Langfuse ≥ 2.0 | LLM trace, token usage, cost, evaluation scores |
| **API** | FastAPI ≥ 0.115 | REST interface for ticket submission and retrieval |
| **UI** | Gradio | Demo/testing interface |
| **Orchestration** | Airflow | Policy ingestion + memory indexing + evaluation DAGs |
| **Infrastructure** | Terraform + AWS ECS/RDS | Production deployment |

---

## Memory Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Three Memory Layers                 │
│                                                      │
│  Short-term  ──  AgentState (in-process TypedDict)   │
│                  Scoped to one ticket run             │
│                                                      │
│  Long-term   ──  SQLite / PostgreSQL                 │
│                  Customers, tickets, escalations,    │
│                  agent logs, conversations            │
│                                                      │
│  Semantic    ──  ChromaDB TICKETS_COLLECTION         │
│                  Resolved ticket embeddings for       │
│                  similar-case retrieval               │
└──────────────────────────────────────────────────────┘
```

**load_memory(db, ticket)** → fetches long-term + semantic context into `MemoryContext` before the graph starts.  
**save_memory(db, state)** → persists classification, routing, escalation, logs, and messages after the graph completes.

---

## RAG Architecture

```
data/policies/*.md  ──►  document_loader  ──►  text_extractor
                                                     │
                                               chunker (500 chars / 50 overlap)
                                                     │
                                               embeddings (text-embedding-3-small)
                                                     │
                                         ChromaDB policy_documents collection
                                                     │
                          retrieve_policy node  ◄────┘  (top-5 chunks)
                                                     │
                                        context_formatter  ──►  LLM prompt
```

---

## Decision Logic

```
classify_ticket  ──►  TicketCategory  ──►  CATEGORY_TO_DEPARTMENT map
                                │
                        confidence_score
                                │
              ┌─────────────────┴──────────────────┐
              │  score ≥ 0.75 AND no escalation     │  score < 0.75 OR
              │         keywords                    │  keyword match
              ▼                                     ▼
        route_ticket                        escalate_ticket
        (Billing Team /                     (Human Review Queue)
         Tech Support /
         Customer Success /
         Product Team)
```

**Escalation keywords** (always force escalation regardless of confidence):
`legal`, `lawsuit`, `lawyer`, `fraud`, `gdpr`, `data breach`, `unauthorized charge`, `threatening`, `harassment`, and others — see `config/constants.py`.

**High-value refund threshold:** > $500 → escalation required.

---

## Data Flow per Ticket

```
1.  Receive      TicketInput arrives (ticket_id, customer_id, subject, message)
2.  Load memory  CustomerHistory + SimilarCases fetched
3.  Classify     LLM assigns TicketCategory + confidence_score
4.  Retrieve     Top-5 policy chunks fetched from ChromaDB
5.  Draft        LLM generates customer-facing response using policy context
6.  Check        confidence_score vs threshold + escalation keyword scan
7a. Route        Low-risk → assigned to handling department
7b. Escalate     High-risk → packaged for human reviewer
8.  Summarize    LLM writes 1-sentence summary for audit log
9.  Store        Ticket, agent log, escalation (if any), messages → DB
10. Trace        All LLM calls + decisions logged to Langfuse
```

---

## File Structure (implemented phases)

```
ai-customer-support-agent/
├── config/          settings.py, constants.py
├── agents/          state.py, graph.py (Phase 7), nodes/ (Phase 7)
├── api/             schemas/ (ticket, response, routing, escalation, memory, eval)
├── rag/             document_loader, text_extractor, chunker, embeddings,
│                    vector_store, retriever, metadata_filter, context_formatter
├── memory/          memory_manager, memory_retriever, short_term, long_term,
│                    semantic, conversation_history, customer_history, ticket_memory
├── database/        models.py, db.py, session.py  +  8 tables via Alembic
├── data/
│   ├── policies/    billing_policy.md, refund_policy.md,
│   │                technical_support_guide.md, support_faq.md
│   ├── tickets/     sample_tickets.json (18 tickets)
│   ├── history/     customer_history.json, historical_tickets.json,
│   │                historical_resolutions.json
│   └── evaluation/  eval_cases.json (10 cases)
├── scripts/         ingest_documents.py, ingest_memory.py, seed_database.py
├── tests/           test_retrieval.py (57 tests), test_memory.py (48 tests)
└── docs/            architecture.md, rag_architecture.md, memory_architecture.md,
                     build_log.md, tech_stack.md, project_checklist.md
```
