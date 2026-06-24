"""Persists the current ticket and final agent decisions to the database.

This module is the write-side of long-term memory. It is called by
memory_manager.save_memory() at the end of each agent graph run to
record what the agent decided and why.
"""
import logging

from sqlalchemy.orm import Session

from api.schemas.ticket_schema import TicketInput
from database.models import AgentLog, Escalation, Ticket
from memory.long_term_memory import get_or_create_customer, save_ticket

logger = logging.getLogger(__name__)


def upsert_ticket(db: Session, ticket_input: TicketInput) -> Ticket:
    """Ensure the ticket exists in the database, creating it if needed.

    Delegates to long_term_memory.save_ticket which is idempotent on ticket_id.
    """
    return save_ticket(db, ticket_input)


def update_ticket_outcome(
    db: Session,
    ticket_id: str,
    classification: str,
    confidence_score: float,
    routing_decision: str,
    escalation_required: bool,
    status: str = "resolved",
) -> Ticket | None:
    """Write the agent's final classification and routing decision onto the ticket row.

    Sets status to "resolved" by default; pass status="escalated" when
    the ticket is routed to human review.
    """
    ticket = db.query(Ticket).filter_by(ticket_id=ticket_id).first()
    if not ticket:
        logger.warning("Ticket %s not found — skipping outcome update.", ticket_id)
        return None

    ticket.classification = classification
    ticket.confidence_score = confidence_score
    ticket.status = "escalated" if escalation_required else status
    db.commit()
    db.refresh(ticket)
    logger.info(
        "Updated outcome for ticket %s: %s (%.2f) → status=%s",
        ticket_id,
        classification,
        confidence_score,
        ticket.status,
    )
    return ticket


def log_agent_decision(
    db: Session,
    ticket_id: str,
    classification: str | None,
    confidence_score: float,
    routing_decision: str | None,
    escalation_required: bool,
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    processing_time_ms: int = 0,
    langfuse_trace_id: str | None = None,
) -> AgentLog:
    """Insert a row into agent_logs recording the full agent decision.

    Called once per ticket run after the graph completes.
    """
    log = AgentLog(
        ticket_id=ticket_id,
        classification=classification,
        confidence_score=confidence_score,
        routing_decision=routing_decision,
        escalation_required=escalation_required,
        tokens_used=tokens_used,
        cost_usd=cost_usd,
        processing_time_ms=processing_time_ms,
        langfuse_trace_id=langfuse_trace_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    logger.info("Logged agent decision for ticket %s.", ticket_id)
    return log


def save_escalation(
    db: Session,
    ticket_id: str,
    reason: str,
    confidence_score: float,
) -> Escalation:
    """Insert a row into escalations for a ticket that requires human review."""
    escalation = Escalation(
        ticket_id=ticket_id,
        reason=reason,
        confidence_score=confidence_score,
    )
    db.add(escalation)
    db.commit()
    db.refresh(escalation)
    logger.info("Created escalation record for ticket %s.", ticket_id)
    return escalation
