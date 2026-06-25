"""Database CRUD operations.

Thin read/write functions over SQLAlchemy ORM models.
Every function accepts a Session so callers control transaction scope.
Routes and tools use these functions; the memory layer has its own
higher-level wrappers that may call these internally.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from database.models import AgentLog, Customer, Escalation, EvaluationResult, Ticket

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

def get_customer(db: Session, customer_id: str) -> Customer | None:
    """Return the Customer row or None."""
    return db.query(Customer).filter_by(customer_id=customer_id).first()


def get_or_create_customer(
    db: Session,
    customer_id: str,
    *,
    email: str | None = None,
    name: str | None = None,
) -> Customer:
    """Return existing Customer or insert a new one (idempotent)."""
    customer = db.query(Customer).filter_by(customer_id=customer_id).first()
    if not customer:
        customer = Customer(customer_id=customer_id, email=email, name=name)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        logger.info("Created customer record: %s", customer_id)
    return customer


# ---------------------------------------------------------------------------
# Ticket
# ---------------------------------------------------------------------------

def get_ticket(db: Session, ticket_id: str) -> Ticket | None:
    """Return the Ticket row or None."""
    return db.query(Ticket).filter_by(ticket_id=ticket_id).first()


def create_ticket(
    db: Session,
    *,
    ticket_id: str,
    customer_id: str,
    subject: str,
    message: str,
    channel: str,
    priority: str,
    classification: str | None = None,
    confidence_score: float | None = None,
    status: str = "open",
) -> Ticket:
    """Insert a new ticket row.

    Returns the existing row unchanged if ticket_id already exists (idempotent).
    Ensures the parent Customer row exists before inserting.
    """
    existing = db.query(Ticket).filter_by(ticket_id=ticket_id).first()
    if existing:
        return existing
    get_or_create_customer(db, customer_id)
    ticket = Ticket(
        ticket_id=ticket_id,
        customer_id=customer_id,
        subject=subject,
        message=message,
        channel=channel,
        priority=priority,
        classification=classification,
        confidence_score=confidence_score,
        status=status,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    logger.info("Created ticket %s", ticket_id)
    return ticket


def update_ticket_classification(
    db: Session,
    ticket_id: str,
    classification: str,
    confidence_score: float,
) -> Ticket | None:
    """Set classification and confidence_score on an existing Ticket row."""
    ticket = db.query(Ticket).filter_by(ticket_id=ticket_id).first()
    if ticket:
        ticket.classification = classification
        ticket.confidence_score = confidence_score
        db.commit()
        db.refresh(ticket)
    return ticket


def update_ticket_status(db: Session, ticket_id: str, status: str) -> Ticket | None:
    """Set the status field on an existing Ticket row."""
    ticket = db.query(Ticket).filter_by(ticket_id=ticket_id).first()
    if ticket:
        ticket.status = status
        db.commit()
        db.refresh(ticket)
    return ticket


def get_customer_history(
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


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

def create_escalation(
    db: Session,
    *,
    ticket_id: str,
    reason: str,
    confidence_score: float,
    resolved: bool = False,
    resolved_by: str | None = None,
) -> Escalation:
    """Insert a new escalation record for the given ticket."""
    esc = Escalation(
        ticket_id=ticket_id,
        reason=reason,
        confidence_score=confidence_score,
        resolved=resolved,
        resolved_by=resolved_by,
    )
    db.add(esc)
    db.commit()
    db.refresh(esc)
    logger.info("Created escalation for ticket %s", ticket_id)
    return esc


def get_escalation(db: Session, ticket_id: str) -> Escalation | None:
    """Return the most recent escalation row for a ticket or None."""
    return (
        db.query(Escalation)
        .filter_by(ticket_id=ticket_id)
        .order_by(Escalation.created_at.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# AgentLog
# ---------------------------------------------------------------------------

def create_agent_log(
    db: Session,
    *,
    ticket_id: str,
    classification: str | None = None,
    confidence_score: float | None = None,
    routing_decision: str | None = None,
    escalation_required: bool = False,
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    processing_time_ms: int = 0,
    langfuse_trace_id: str | None = None,
) -> AgentLog:
    """Insert a new agent_logs row recording the full agent decision."""
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
    logger.info("Created agent log for ticket %s", ticket_id)
    return log


# ---------------------------------------------------------------------------
# EvaluationResult
# ---------------------------------------------------------------------------

def create_evaluation_result(
    db: Session,
    *,
    case_id: str,
    ticket_id: str,
    classification_correct: bool,
    routing_correct: bool,
    escalation_correct: bool,
    confidence_score: float,
    processing_time_ms: int = 0,
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    langfuse_trace_id: str | None = None,
) -> EvaluationResult:
    """Insert a new evaluation_results row."""
    result = EvaluationResult(
        case_id=case_id,
        ticket_id=ticket_id,
        classification_correct=classification_correct,
        routing_correct=routing_correct,
        escalation_correct=escalation_correct,
        confidence_score=confidence_score,
        processing_time_ms=processing_time_ms,
        tokens_used=tokens_used,
        cost_usd=cost_usd,
        langfuse_trace_id=langfuse_trace_id,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    logger.info("Created evaluation result for case %s / ticket %s", case_id, ticket_id)
    return result


def get_evaluation_results(
    db: Session,
    ticket_id: str | None = None,
) -> list[EvaluationResult]:
    """Return evaluation results, optionally filtered to a specific ticket."""
    q = db.query(EvaluationResult)
    if ticket_id:
        q = q.filter_by(ticket_id=ticket_id)
    return q.order_by(EvaluationResult.evaluated_at.desc()).all()
