"""store_memory node — persists agent outputs to SQLite.

Called after summarize_ticket (the last step before log_decision).
Writes:
  - ticket row (upsert — ensures it exists before updating)
  - ticket outcome (classification, routing, status)
  - agent decision log row (agent_logs table)
  - escalation record (if escalation_required)

Uses ticket_memory directly instead of memory_manager.save_memory so
the node can be called independently in tests.
"""
import logging

from agents.state import AgentState
from database.session import SessionLocal
from memory.ticket_memory import (
    log_agent_decision,
    save_escalation,
    update_ticket_outcome,
    upsert_ticket,
)

logger = logging.getLogger(__name__)


def store_memory_node(state: AgentState) -> dict:
    """Persist classification, routing, and agent log to the database."""
    ticket = state["ticket"]
    classification = state.get("classification", "")
    confidence = float(state.get("confidence_score", 0.0))
    routing = state.get("routing_decision", "")
    escalation_required = bool(state.get("escalation_required", False))
    escalation_reason = state.get("escalation_reason", "")
    langfuse_trace_id = state.get("langfuse_trace_id", "") or None

    db = SessionLocal()
    try:
        # Ensure the ticket row exists before any FK-dependent writes
        upsert_ticket(db, ticket)

        update_ticket_outcome(
            db,
            ticket_id=ticket.ticket_id,
            classification=classification,
            confidence_score=confidence,
            routing_decision=routing,
            escalation_required=escalation_required,
        )

        log_agent_decision(
            db,
            ticket_id=ticket.ticket_id,
            classification=classification,
            confidence_score=confidence,
            routing_decision=routing,
            escalation_required=escalation_required,
            langfuse_trace_id=langfuse_trace_id,
        )

        if escalation_required and escalation_reason:
            save_escalation(
                db,
                ticket_id=ticket.ticket_id,
                reason=escalation_reason,
                confidence_score=confidence,
            )

        logger.info("Stored memory for ticket %s.", ticket.ticket_id)

    except Exception as exc:
        logger.error("store_memory failed for ticket %s: %s", ticket.ticket_id, exc)
    finally:
        db.close()

    return {
        "audit_log": {
            **state.get("audit_log", {}),
            "memory_stored": True,
        }
    }
