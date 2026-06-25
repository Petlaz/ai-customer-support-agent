"""log_decision_tool — LangChain tool that writes an agent decision to the DB.

Inserts a row into agent_logs recording the full classification, routing,
token usage, cost, and optional Langfuse trace ID.
"""
import logging
from datetime import datetime, timezone

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from memory.ticket_memory import log_agent_decision

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class LogDecisionInput(BaseModel):
    ticket_id: str = Field(..., description="Ticket identifier")
    classification: str = Field(default="", description="Ticket category")
    confidence_score: float = Field(default=0.0, description="Confidence 0.0–1.0")
    routing_decision: str = Field(default="", description="Assigned department")
    escalation_required: bool = Field(default=False)
    tokens_used: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    langfuse_trace_id: str = Field(default="", description="Optional Langfuse trace ID")


class LogDecisionOutput(BaseModel):
    log_id: int | None = None
    logged: bool
    logged_at: str


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def log_decision(
    ticket_id: str,
    classification: str = "",
    confidence_score: float = 0.0,
    routing_decision: str = "",
    escalation_required: bool = False,
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    langfuse_trace_id: str = "",
) -> dict:
    """Write an agent decision log entry to the database.

    Records classification, routing, escalation status, token usage, cost,
    and Langfuse trace ID in the agent_logs table.
    """
    from database.session import SessionLocal  # noqa: PLC0415

    db = SessionLocal()
    try:
        log = log_agent_decision(
            db,
            ticket_id=ticket_id,
            classification=classification or None,
            confidence_score=confidence_score,
            routing_decision=routing_decision or None,
            escalation_required=escalation_required,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            langfuse_trace_id=langfuse_trace_id or None,
        )
        logger.info("log_decision: logged decision for ticket %s (log_id=%s).", ticket_id, log.id)
        return LogDecisionOutput(
            log_id=log.id,
            logged=True,
            logged_at=datetime.now(timezone.utc).isoformat(),
        ).model_dump()
    except Exception as exc:
        logger.error("log_decision failed for ticket %s: %s", ticket_id, exc)
        return LogDecisionOutput(
            log_id=None,
            logged=False,
            logged_at=datetime.now(timezone.utc).isoformat(),
        ).model_dump()
    finally:
        db.close()
