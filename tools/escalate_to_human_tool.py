"""escalate_to_human_tool — LangChain tool that creates an escalation record.

Inserts a row into the escalations table and returns the escalation ID,
assigned queue, and timestamp.  Called when the agent determines the ticket
requires human review.
"""
import logging
from datetime import datetime, timezone

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from config.constants import Department
from memory.ticket_memory import save_escalation

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class EscalateToHumanInput(BaseModel):
    ticket_id: str = Field(..., description="Ticket to escalate")
    reason: str = Field(..., description="Escalation reason")
    confidence_score: float = Field(..., description="Agent confidence score", ge=0.0, le=1.0)


class EscalateToHumanOutput(BaseModel):
    escalated: bool
    escalation_id: int | None = None
    assigned_queue: str
    escalated_at: str


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def escalate_to_human(
    ticket_id: str,
    reason: str,
    confidence_score: float,
) -> dict:
    """Create an escalation record in the database and assign the ticket to human review.

    Returns the escalation_id, assigned_queue, and timestamp.
    """
    from database.session import SessionLocal  # noqa: PLC0415

    db = SessionLocal()
    try:
        escalation = save_escalation(db, ticket_id=ticket_id, reason=reason, confidence_score=confidence_score)
        logger.warning("escalate_to_human: ticket %s escalated — %s", ticket_id, reason)
        return EscalateToHumanOutput(
            escalated=True,
            escalation_id=escalation.id,
            assigned_queue=Department.HUMAN_REVIEW_QUEUE.value,
            escalated_at=datetime.now(timezone.utc).isoformat(),
        ).model_dump()
    except Exception as exc:
        logger.error("escalate_to_human failed for ticket %s: %s", ticket_id, exc)
        return EscalateToHumanOutput(
            escalated=False,
            escalation_id=None,
            assigned_queue=Department.HUMAN_REVIEW_QUEUE.value,
            escalated_at=datetime.now(timezone.utc).isoformat(),
        ).model_dump()
    finally:
        db.close()
