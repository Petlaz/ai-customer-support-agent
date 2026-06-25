"""retrieve_long_term_memory node — fetches customer history from SQLite.

Queries the tickets + escalations tables for the customer's prior support
record. The resulting CustomerHistory is serialised to a list of dicts so
it can live safely inside the AgentState TypedDict.
"""
import logging

from agents.state import AgentState
from database.session import SessionLocal
from memory.customer_history import get_customer_history

logger = logging.getLogger(__name__)


def retrieve_long_term_memory_node(state: AgentState) -> dict:
    """Fetch the customer's prior ticket history from the database."""
    ticket = state["ticket"]

    db = SessionLocal()
    try:
        history = get_customer_history(db, ticket.customer_id)
    finally:
        db.close()

    history_dicts = [
        {
            "ticket_id": t.ticket_id,
            "subject": t.subject,
            "classification": t.classification,
            "resolution": t.resolution,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in history.tickets
    ]

    logger.info(
        "Customer %s history: %d prior tickets, %d escalations, %d refunds.",
        ticket.customer_id,
        history.total_tickets,
        history.previous_escalations,
        history.previous_refunds,
    )

    return {
        "customer_history": history_dicts,
        "audit_log": {
            **state.get("audit_log", {}),
            "customer_total_tickets": history.total_tickets,
            "customer_prior_escalations": history.previous_escalations,
            "customer_prior_refunds": history.previous_refunds,
        },
    }
