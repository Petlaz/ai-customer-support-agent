"""draft_response node — generates a customer-facing response via LLM.

Combines the retrieved policy context, similar resolved cases, and
customer history into the DRAFT_RESPONSE_PROMPT and calls the LLM.

Falls back to a template message when the LLM is unavailable.

Langfuse: the LLM call is traced via a CallbackHandler linked to the
workflow trace, capturing prompt, completion, tokens, latency, and cost.
"""
import logging

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from agents.prompts import DRAFT_RESPONSE_PROMPT
from agents.state import AgentState
from config.constants import TEMPERATURE
from config.settings import settings
from observability.langfuse_client import estimate_cost, get_callback_handler

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


def _extract_token_usage(response) -> tuple[int, int]:
    """Pull prompt + completion token counts from an AIMessage (if available)."""
    usage: dict = {}
    if hasattr(response, "response_metadata"):
        usage = response.response_metadata.get("token_usage", {})
    if not usage and hasattr(response, "usage_metadata") and response.usage_metadata:
        usage = response.usage_metadata
    prompt_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)))
    completion_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)))
    return prompt_tokens, completion_tokens


def draft_response_node(state: AgentState) -> dict:
    """Draft a customer-facing response using the LLM."""
    ticket = state["ticket"]
    trace_id = state.get("langfuse_trace_id") or None

    policy_context = "\n\n".join(state.get("retrieved_policies", [])) or "No policy documents available."
    similar_text = _format_similar_cases(state.get("similar_cases", []))
    history_text = _format_customer_history(state.get("customer_history", []))

    handler = get_callback_handler(trace_id)
    callbacks = [handler] if handler else []

    prompt_tokens = completion_tokens = 0

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
            },
            config={"callbacks": callbacks},
        )
        draft = response.content.strip()
        prompt_tokens, completion_tokens = _extract_token_usage(response)
        logger.info("Drafted response for ticket %s (%d chars).", ticket.ticket_id, len(draft))

    except Exception as exc:
        logger.warning(
            "LLM draft generation failed for ticket %s: %s — using fallback.",
            ticket.ticket_id,
            exc,
        )
        draft = _FALLBACK_RESPONSE

    ai_msg = AIMessage(content=draft, additional_kwargs={"node": "draft_response"})
    cost_usd = estimate_cost(prompt_tokens, completion_tokens)

    return {
        "draft_response": draft,
        "messages": [ai_msg],
        "audit_log": {
            **state.get("audit_log", {}),
            "draft_length_chars": len(draft),
            "draft_prompt_tokens": prompt_tokens,
            "draft_completion_tokens": completion_tokens,
            "draft_cost_usd": cost_usd,
        },
    }


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
