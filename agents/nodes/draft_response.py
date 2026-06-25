"""draft_response node — generates a customer-facing response via LLM.

Combines the retrieved policy context, similar resolved cases, and
customer history into the DRAFT_RESPONSE_PROMPT and calls the LLM.

Falls back to a template message when the LLM is unavailable.
"""
import logging

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from agents.prompts import DRAFT_RESPONSE_PROMPT
from agents.state import AgentState
from config.constants import TEMPERATURE
from config.settings import settings

logger = logging.getLogger(__name__)

_FALLBACK_RESPONSE = (
    "Thank you for contacting Nexus Software Support.\n\n"
    "We have received your ticket and a member of our team will review it shortly. "
    "We apologise for any inconvenience and will get back to you as soon as possible.\n\n"
    "If this is urgent, please reply to this message and we will prioritise your case."
)


def _format_similar_cases(cases: list[dict]) -> str:
    if not cases:
        return "No similar resolved cases found."
    lines: list[str] = []
    for c in cases[:3]:
        score = c.get("similarity_score", 0)
        resolution = c.get("resolution", "N/A")
        lines.append(
            f"- [{c.get('classification', 'Unknown')}] {c.get('subject', '')} "
            f"(similarity={score:.2f}): {resolution}"
        )
    return "\n".join(lines)


def _format_customer_history(history: list[dict]) -> str:
    if not history:
        return "No prior interactions."
    lines = [
        f"- [{h.get('classification', 'Unknown')}] {h.get('subject', '')} "
        f"({str(h.get('created_at', ''))[:10]})"
        for h in history[:3]
    ]
    return "\n".join(lines)


def draft_response_node(state: AgentState) -> dict:
    """Draft a customer-facing response using the LLM."""
    ticket = state["ticket"]

    policy_context = "\n\n".join(state.get("retrieved_policies", [])) or "No policy documents available."
    similar_text = _format_similar_cases(state.get("similar_cases", []))
    history_text = _format_customer_history(state.get("customer_history", []))

    try:
        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=TEMPERATURE,
        )
        chain = DRAFT_RESPONSE_PROMPT | llm

        response = chain.invoke(
            {
                "classification": state.get("classification", "Unknown"),
                "subject": ticket.subject,
                "message": ticket.message,
                "policy_context": policy_context,
                "similar_cases": similar_text,
                "customer_history": history_text,
            }
        )
        draft = response.content.strip()
        logger.info("Drafted response for ticket %s (%d chars).", ticket.ticket_id, len(draft))

    except Exception as exc:
        logger.warning(
            "LLM draft generation failed for ticket %s: %s — using fallback.",
            ticket.ticket_id,
            exc,
        )
        draft = _FALLBACK_RESPONSE

    ai_msg = AIMessage(content=draft, additional_kwargs={"node": "draft_response"})

    return {
        "draft_response": draft,
        "messages": [ai_msg],
        "audit_log": {
            **state.get("audit_log", {}),
            "draft_length_chars": len(draft),
        },
    }
