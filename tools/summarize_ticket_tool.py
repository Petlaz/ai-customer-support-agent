"""summarize_ticket_tool — LangChain tool that generates a one-sentence audit summary.

Calls GPT-4o-mini with SUMMARIZE_PROMPT to produce an internal audit log
entry.  Falls back to a formatted template when the LLM is unavailable.
"""
import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agents.nodes.summarize_ticket import _extract_token_usage
from agents.prompts import SUMMARIZE_PROMPT
from config.constants import TEMPERATURE
from config.settings import settings

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class SummarizeTicketInput(BaseModel):
    subject: str = Field(..., description="Ticket subject")
    classification: str = Field(..., description="Ticket category")
    customer_id: str = Field(..., description="Customer identifier")
    routing_decision: str = Field(..., description="Assigned department or queue")
    escalated: bool = Field(default=False, description="Whether the ticket was escalated")
    draft_response: str = Field(default="", description="Draft customer-facing response")


class SummarizeTicketOutput(BaseModel):
    summary: str = Field(description="One-sentence internal audit summary")


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def summarize_ticket(
    subject: str,
    classification: str,
    customer_id: str,
    routing_decision: str,
    escalated: bool = False,
    draft_response: str = "",
) -> dict:
    """Generate a one-sentence internal audit summary for a resolved or routed ticket.

    Returns a concise factual summary suitable for the agent_logs table.
    Falls back to a formatted template when the LLM is unavailable.
    """
    try:
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=TEMPERATURE,
        )
        chain = SUMMARIZE_PROMPT | llm
        response = chain.invoke(
            {
                "subject": subject,
                "classification": classification,
                "customer_id": customer_id,
                "routing_decision": routing_decision,
                "escalated": str(escalated),
                "draft_response": draft_response[:500],
            }
        )
        summary = response.content.strip()
        logger.info("summarize_ticket: generated summary for customer %s.", customer_id)
        return SummarizeTicketOutput(summary=summary).model_dump()

    except Exception as exc:
        logger.warning("summarize_ticket LLM failed: %s — fallback.", exc)
        escalation_note = " Escalated for human review." if escalated else ""
        fallback = (
            f"{classification} ticket from customer {customer_id} "
            f"re: {subject[:60]}. Routed to {routing_decision}.{escalation_note}"
        )
        return SummarizeTicketOutput(summary=fallback).model_dump()
