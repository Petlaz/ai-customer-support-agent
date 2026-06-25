"""summarize_ticket node — generates a one-sentence audit summary via LLM.

Called after route_ticket or escalate_ticket.  The summary is written to
state["summary"] and also to the audit_log for storage in the DB.

Falls back to a formatted template when the LLM is unavailable.

Langfuse: the LLM call is traced via a CallbackHandler linked to the
workflow trace, capturing prompt, completion, tokens, latency, and cost.
"""
import logging

from langchain_openai import ChatOpenAI

from agents.prompts import SUMMARIZE_PROMPT
from agents.state import AgentState
from config.constants import TEMPERATURE
from config.settings import settings
from observability.langfuse_client import estimate_cost, get_callback_handler

logger = logging.getLogger(__name__)


def _extract_token_usage(response) -> tuple[int, int]:
    usage: dict = {}
    if hasattr(response, "response_metadata"):
        usage = response.response_metadata.get("token_usage", {})
    if not usage and hasattr(response, "usage_metadata") and response.usage_metadata:
        usage = response.usage_metadata
    prompt_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)))
    completion_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)))
    return prompt_tokens, completion_tokens


def summarize_ticket_node(state: AgentState) -> dict:
    """Generate a one-sentence internal audit summary for the ticket."""
    ticket = state["ticket"]
    trace_id = state.get("langfuse_trace_id") or None
    classification = state.get("classification", "Unknown")
    routing = state.get("routing_decision", "Unknown")
    escalated = state.get("escalation_required", False)
    draft = state.get("draft_response", "")[:500]  # truncate for prompt

    handler = get_callback_handler(trace_id)
    callbacks = [handler] if handler else []

    prompt_tokens = completion_tokens = 0

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
            },
            config={"callbacks": callbacks},
        )
        summary = response.content.strip()
        prompt_tokens, completion_tokens = _extract_token_usage(response)
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

    cost_usd = estimate_cost(prompt_tokens, completion_tokens)
    audit = state.get("audit_log", {})

    return {
        "summary": summary,
        "audit_log": {
            **audit,
            "summary": summary,
            "summarize_prompt_tokens": prompt_tokens,
            "summarize_completion_tokens": completion_tokens,
            "summarize_cost_usd": cost_usd,
            "total_tokens": (
                audit.get("draft_prompt_tokens", 0)
                + audit.get("draft_completion_tokens", 0)
                + prompt_tokens
                + completion_tokens
            ),
            "total_cost_usd": round(
                audit.get("draft_cost_usd", 0.0) + cost_usd, 8
            ),
        },
    }



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
