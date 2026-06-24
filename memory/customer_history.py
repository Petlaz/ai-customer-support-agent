"""Retrieves a customer's full support history from the database.

Queries the tickets and escalations tables to build a CustomerHistory
schema that the agent uses to personalise its response — e.g. waiving
a fee for a long-standing customer, or flagging a customer with many
prior escalations for immediate human review.
"""
import logging

from sqlalchemy.orm import Session

from api.schemas.memory_schema import CustomerHistory, PreviousTicket
from database.models import Escalation, Ticket

logger = logging.getLogger(__name__)


def get_customer_history(
    db: Session,
    customer_id: str,
    limit: int = 10,
) -> CustomerHistory:
    """Return a CustomerHistory schema populated from the database.

    Args:
        db:          Active SQLAlchemy session.
        customer_id: The customer whose history to retrieve.
        limit:       Maximum number of previous tickets to return.

    Returns:
        CustomerHistory with tickets, total_tickets, previous_escalations,
        and previous_refunds counts.
    """
    # Fetch most recent tickets for this customer
    tickets = (
        db.query(Ticket)
        .filter_by(customer_id=customer_id)
        .order_by(Ticket.created_at.desc())
        .limit(limit)
        .all()
    )

    previous_tickets = [
        PreviousTicket(
            ticket_id=t.ticket_id,
            subject=t.subject,
            classification=t.classification or "Unknown",
            # resolution is populated in Phase 11 when AgentResponse is persisted
            resolution=None,
            created_at=t.created_at,
        )
        for t in tickets
    ]

    # Count total escalations across all of this customer's tickets
    escalation_count = (
        db.query(Escalation)
        .join(Ticket, Escalation.ticket_id == Ticket.ticket_id)
        .filter(Ticket.customer_id == customer_id)
        .count()
    )

    # Count tickets classified as Refund
    refund_count = (
        db.query(Ticket)
        .filter(
            Ticket.customer_id == customer_id,
            Ticket.classification == "Refund",
        )
        .count()
    )

    logger.info(
        "Customer %s history: %d tickets, %d escalations, %d refunds.",
        customer_id,
        len(previous_tickets),
        escalation_count,
        refund_count,
    )

    return CustomerHistory(
        customer_id=customer_id,
        tickets=previous_tickets,
        total_tickets=len(previous_tickets),
        previous_escalations=escalation_count,
        previous_refunds=refund_count,
    )
