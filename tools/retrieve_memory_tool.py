"""retrieve_memory_tool — LangChain tool that fetches customer history from the DB.

Queries the tickets and escalations tables and returns a CustomerHistory
payload containing prior tickets, escalation count, and refund count.
"""
import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from memory.customer_history import get_customer_history

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class RetrieveMemoryInput(BaseModel):
    customer_id: str = Field(..., description="Customer identifier")
    limit: int = Field(default=10, description="Max prior tickets to return", ge=1, le=50)


class RetrieveMemoryOutput(BaseModel):
    customer_history: list[dict] = Field(default_factory=list, description="Prior tickets list")
    total_tickets: int = Field(description="Total tickets submitted by this customer")
    prior_escalations: int = Field(description="Number of prior escalations")
    prior_refunds: int = Field(description="Number of prior refunds")


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def retrieve_memory(
    customer_id: str,
    limit: int = 10,
) -> dict:
    """Retrieve a customer's full ticket history and escalation/refund counts from the database.

    Returns prior tickets, total_tickets, prior_escalations, and prior_refunds.
    """
    from database.session import SessionLocal  # noqa: PLC0415

    db = SessionLocal()
    try:
        history = get_customer_history(db, customer_id, limit)
        tickets = [
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
            "retrieve_memory: customer %s — %d tickets, %d escalations.",
            customer_id,
            history.total_tickets,
            history.previous_escalations,
        )
        return RetrieveMemoryOutput(
            customer_history=tickets,
            total_tickets=history.total_tickets,
            prior_escalations=history.previous_escalations,
            prior_refunds=history.previous_refunds,
        ).model_dump()
    except Exception as exc:
        logger.error("retrieve_memory failed for customer %s: %s", customer_id, exc)
        return RetrieveMemoryOutput(
            customer_history=[],
            total_tickets=0,
            prior_escalations=0,
            prior_refunds=0,
        ).model_dump()
    finally:
        db.close()
