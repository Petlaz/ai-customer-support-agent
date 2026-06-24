# Memory Architecture

## Overview

The memory layer gives the agent awareness of context beyond the current ticket. It implements three memory types that work together:

| Type | Storage | Scope | Purpose |
|------|---------|-------|---------|
| **Short-term** | `AgentState` (in-process) | Single ticket run | In-flight classification, response, routing decisions |
| **Long-term** | SQLite (`data/support_agent.db`) | Persistent across runs | Customer history, ticket outcomes, escalation records |
| **Semantic** | ChromaDB (`data/chroma_db/`) | Persistent across runs | Similarity search over resolved historical tickets |

---

## Architecture

```
Incoming ticket
      │
      ▼
memory_manager.load_memory(db, ticket)
      │
      ├── ticket_memory.upsert_ticket()          ← ensure ticket row exists in DB
      │
      └── memory_retriever.retrieve_memory_context()
              │
              ├── customer_history.get_customer_history()
              │       └── queries: tickets + escalations tables
              │           returns: CustomerHistory(tickets, escalation_count, refund_count)
              │
              └── semantic_memory.retrieve_similar()
                      └── queries: ChromaDB TICKETS_COLLECTION
                          returns: list[SimilarCase] with similarity_score
              │
              ▼
         MemoryContext  ──→  injected into AgentState
                             (customer_history, similar_cases)

Agent graph runs (Phase 7)...

      │
      ▼
memory_manager.save_memory(db, state)
      │
      ├── ticket_memory.update_ticket_outcome()   ← classification, routing, status
      ├── ticket_memory.log_agent_decision()      ← tokens, cost, latency, trace ID
      ├── ticket_memory.save_escalation()         ← only if escalation_required=True
      └── conversation_history.save_messages_to_db()  ← HumanMessage + AIMessage rows
```

---

## Files

| File | Responsibility |
|------|---------------|
| `memory/short_term_memory.py` | Read/write helpers for `AgentState` fields; returns partial state dicts for LangGraph nodes |
| `memory/long_term_memory.py` | Low-level SQLAlchemy CRUD: `get_or_create_customer`, `save_ticket`, `get_customer_tickets`, `update_ticket_classification` |
| `memory/semantic_memory.py` | `index_ticket` / `index_tickets_batch` — embed and store resolved tickets; `retrieve_similar` — similarity search |
| `memory/conversation_history.py` | `build_human_message` / `build_ai_message` — LangChain message constructors; `format_history` — transcript formatter; `save_messages_to_db` — DB persistence |
| `memory/customer_history.py` | `get_customer_history` — returns `CustomerHistory` schema with ticket list, escalation count, refund count |
| `memory/ticket_memory.py` | Write-side: `upsert_ticket`, `update_ticket_outcome`, `log_agent_decision`, `save_escalation` |
| `memory/memory_retriever.py` | Unified read entry point — calls `customer_history` + `semantic_memory` → `MemoryContext` |
| `memory/memory_manager.py` | Agent interface: `load_memory(db, ticket)` and `save_memory(db, state)` |

---

## Schemas

```python
# api/schemas/memory_schema.py

class PreviousTicket:
    ticket_id, subject, classification, resolution, created_at

class CustomerHistory:
    customer_id, tickets: list[PreviousTicket]
    total_tickets, previous_escalations, previous_refunds

class SimilarCase:
    ticket_id, subject, message, classification, resolution
    similarity_score: float  # 0.0–1.0, derived from: 1 / (1 + chroma_distance)

class MemoryContext:
    customer_history: CustomerHistory
    similar_cases: list[SimilarCase]
```

---

## Database Tables Used

| Table | Read | Write |
|-------|------|-------|
| `customers` | — | `get_or_create_customer` |
| `tickets` | `get_customer_tickets` | `save_ticket`, `update_ticket_outcome` |
| `escalations` | `get_customer_history` (count) | `save_escalation` |
| `agent_logs` | — | `log_agent_decision` |
| `conversations` | — | `save_messages_to_db` |

---

## Similarity Score

ChromaDB returns a distance value (lower = more similar). The memory layer converts it to a similarity score in [0, 1]:

$$\text{similarity} = \frac{1}{1 + \text{distance}}$$

A distance of 0 (identical) → similarity of 1.0. A large distance → similarity approaching 0.

---

## Agent Interface (How Phase 7 uses this)

```python
# At the start of the graph — retrieve_long_term_memory node
context = memory_manager.load_memory(db, state["ticket"])
# → returns MemoryContext; node adds it to AgentState

# At the end of the graph — store_memory node
memory_manager.save_memory(db, state)
# → writes all outputs to DB
```

---

## Populating Semantic Memory

Historical tickets are not automatically indexed. To seed the `historical_tickets` collection:

```python
from memory.semantic_memory import index_tickets_batch

tickets = [
    {
        "ticket_id": "TKT-001",
        "text": "Billing dispute — duplicate charge on invoice. Resolved with full refund.",
        "classification": "Billing",
        "subject": "Duplicate charge",
        "resolution": "Full refund issued",
    },
    ...
]
index_tickets_batch(tickets)
```

The Airflow `memory_indexing_dag.py` will automate this in Phase 12.
