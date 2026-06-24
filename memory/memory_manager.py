"""Memory manager — single entry point for all memory operations during agent execution.

Agent nodes call only two functions from this module:
  - load_memory(db, ticket)  → MemoryContext  (called before the graph starts)
  - save_memory(db, state)   → None           (called after the graph completes)

All other memory sub-modules (long_term_memory, semantic_memory, ticket_memory,
conversation_history) are internal implementation details.
"""
import logging

from sqlalchemy.orm import Session

from agents.state import AgentState
from api.schemas.memory_schema import MemoryContext
from api.schemas.ticket_schema import TicketInput
from memory.conversation_history import save_messages_to_db
from memory.memory_retriever import retrieve_memory_context
from memory.ticket_memory import (
    log_agent_decision,
    save_escalation,
    update_ticket_outcome,
    upsert_ticket,
)

logger = logging.getLogger(__name__)


def load_memory(db: Session, ticket: TicketInput) -> MemoryContext:
    """Load all memory context needed before the agent graph starts.

    Steps:
    1. Ensure the ticket row exists in the database (idempotent upsert).
    2. Fetch customer history (prior tickets, escalation count, refund count).
    3. Retrieve semantically similar historical tickets from ChromaDB.

    Returns a MemoryContext containing both.
    """
    upsert_ticket(db, ticket)
    context = retrieve_memory_context(db, ticket)
    logger.info(
        "Loaded memory for ticket %s — %d prior tickets, %d similar cases.",
        ticket.ticket_id,
        context.customer_history.total_tickets,
        len(context.similar_cases),
    )
    return context


def save_memory(db: Session, state: AgentState) -> None:
    """Persist all agent outputs after the graph run completes.

    Writes:
    - Final classification + routing → tickets table
    - Full agent decision log → agent_logs table
    - Escalation record (if required) → escalations table
    - Conversation messages (if any) → conversations table

    Safe to call even if the graph did not complete all nodes — missing
    state fields default to empty values.
    """
    ticket = state["ticket"]
    ticket_id = ticket.ticket_id
    audit = state.get("audit_log") or {}

    # 1. Update ticket with final outcome
    update_ticket_outcome(
        db,
        ticket_id=ticket_id,
        classification=state.get("classification", ""),
        confidence_score=state.get("confidence_score", 0.0),
        routing_decision=state.get("routing_decision", ""),
        escalation_required=state.get("escalation_required", False),
    )

    # 2. Write agent decision log
    log_agent_decision(
        db,
        ticket_id=ticket_id,
        classification=state.get("classification"),
        confidence_score=state.get("confidence_score", 0.0),
        routing_decision=state.get("routing_decision"),
        escalation_required=state.get("escalation_required", False),
        tokens_used=audit.get("tokens_used", 0),
        cost_usd=audit.get("cost_usd", 0.0),
        processing_time_ms=audit.get("processing_time_ms", 0),
        langfuse_trace_id=state.get("langfuse_trace_id"),
    )

    # 3. Save escalation record if required
    if state.get("escalation_required"):
        save_escalation(
            db,
            ticket_id=ticket_id,
            reason=state.get("escalation_reason", ""),
            confidence_score=state.get("confidence_score", 0.0),
        )

    # 4. Save conversation messages
    messages = state.get("messages") or []
    if messages:
        save_messages_to_db(db, ticket_id, ticket.customer_id, messages)

    logger.info("Saved memory for ticket %s.", ticket_id)
