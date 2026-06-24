"""Long-term memory — SQLAlchemy CRUD operations on the Customer and Ticket tables.

Provides low-level read/write functions used by higher-level modules
(customer_history, ticket_memory, memory_manager). Every function
accepts a SQLAlchemy Session so callers control the transaction scope.
"""
import logging

from sqlalchemy.orm import Session

from api.schemas.ticket_schema import TicketInput
from database.models import Customer, Ticket

logger = logging.getLogger(__name__)


# ── Customer ──────────────────────────────────────────────────────────────────


def get_or_create_customer(db: Session, customer_id: str) -> Customer:
    """Return the Customer row for customer_id, creating it if it does not exist."""
    customer = db.query(Customer).filter_by(customer_id=customer_id).first()
    if not customer:
        customer = Customer(customer_id=customer_id)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        logger.info("Created new customer record: %s", customer_id)
    return customer


def get_customer_by_id(db: Session, customer_id: str) -> Customer | None:
    """Return the Customer row or None if not found."""
    return db.query(Customer).filter_by(customer_id=customer_id).first()


# ── Ticket ────────────────────────────────────────────────────────────────────


def get_ticket_by_id(db: Session, ticket_id: str) -> Ticket | None:
    """Return the Ticket row or None if not found."""
    return db.query(Ticket).filter_by(ticket_id=ticket_id).first()


def get_customer_tickets(
    db: Session,
    customer_id: str,
    limit: int = 10,
) -> list[Ticket]:
    """Return the most recent tickets for a customer, newest first."""
    return (
        db.query(Ticket)
        .filter_by(customer_id=customer_id)
        .order_by(Ticket.created_at.desc())
        .limit(limit)
        .all()
    )


def save_ticket(db: Session, ticket_input: TicketInput) -> Ticket:
    """Persist a TicketInput to the database.

    Returns the existing row without modification if the ticket_id already exists.
    Ensures the parent Customer row exists before inserting.
    """
    existing = db.query(Ticket).filter_by(ticket_id=ticket_input.ticket_id).first()
    if existing:
        return existing

    get_or_create_customer(db, ticket_input.customer_id)

    channel = (
        ticket_input.channel.value
        if hasattr(ticket_input.channel, "value")
        else ticket_input.channel
    )
    priority = (
        ticket_input.priority.value
        if hasattr(ticket_input.priority, "value")
        else ticket_input.priority
    )

    ticket = Ticket(
        ticket_id=ticket_input.ticket_id,
        customer_id=ticket_input.customer_id,
        subject=ticket_input.subject,
        message=ticket_input.message,
        channel=channel,
        priority=priority,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    logger.info("Saved ticket %s to database.", ticket.ticket_id)
    return ticket


def update_ticket_classification(
    db: Session,
    ticket_id: str,
    classification: str,
    confidence_score: float,
) -> Ticket | None:
    """Update classification and confidence_score on an existing Ticket row."""
    ticket = db.query(Ticket).filter_by(ticket_id=ticket_id).first()
    if ticket:
        ticket.classification = classification
        ticket.confidence_score = confidence_score
        db.commit()
        db.refresh(ticket)
        logger.info(
            "Updated classification for ticket %s → %s (%.2f)",
            ticket_id,
            classification,
            confidence_score,
        )
    return ticket


def update_ticket_status(
    db: Session,
    ticket_id: str,
    status: str,
) -> Ticket | None:
    """Update the status field on an existing Ticket row."""
    ticket = db.query(Ticket).filter_by(ticket_id=ticket_id).first()
    if ticket:
        ticket.status = status
        db.commit()
        db.refresh(ticket)
    return ticket
