"""summarize_ticket node — generates a one-sentence audit summary via LLM.

Called after route_ticket or escalate_ticket.  The summary is written to
state["summary"] and also to the audit_log for storage in the DB.

Falls back to a formatted template when the LLM is unavailable.
"""
import logging

from langchain_openai import ChatOpenAI

from agents.prompts import SUMMARIZE_PROMPT
from agents.state import AgentState
from config.constants import TEMPERATURE
from config.settings import settings

logger = logging.getLogger(__name__)


def summarize_ticket_node(state: AgentState) -> dict:
    """Generate a one-sentence internal audit summary for the ticket."""
    ticket = state["ticket"]
    classification = state.get("classification", "Unknown")
    routing = state.get("routing_decision", "Unknown")
    escalated = state.get("escalation_required", False)
    draft = state.get("draft_response", "")[:500]  # truncate for prompt

    try:
        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=TEMPERATURE,
        )
        chain = SUMMARIZE_PROMPT | llm

        response = chain.invoke(
            {
                "subject": ticket.subject,
                "classification": classification,
                "customer_id": ticket.customer_id,
                "routing_decision": routing,
                "escalated": str(escalated),
                "draft_response": draft,
            }
        )
        summary = response.content.strip()
        logger.info("Generated summary for ticket %s.", ticket.ticket_id)

    except Exception as exc:
        logger.warning(
            "LLM summarization failed for ticket %s: %s — using fallback.",
            ticket.ticket_id,
            exc,
        )
        escalation_text = " Escalated for human review." if escalated else ""
        summary = (
            f"{classification} ticket from customer {ticket.customer_id} "
            f"re: {ticket.subject[:60]}. Routed to {routing}.{escalation_text}"
        )

    return {
        "summary": summary,
        "audit_log": {
            **state.get("audit_log", {}),
            "summary": summary,
        },
    }
