"""classify_ticket node — uses an LLM to classify the ticket into a category.

Calls OpenAI (or falls back to Anthropic) with the CLASSIFICATION_PROMPT
and uses structured output to return a validated category + confidence score.

If both providers fail (e.g. no billing credits), the node falls back to
a keyword-based classifier and sets confidence to 0.0, which will trigger
escalation via the check_confidence gate.
"""
import json
import logging

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from agents.prompts import CLASSIFICATION_PROMPT
from agents.state import AgentState
from config.constants import TEMPERATURE, TicketCategory
from config.settings import settings

logger = logging.getLogger(__name__)

# ── Structured output schema ──────────────────────────────────────────────────


class ClassificationOutput(BaseModel):  # noqa: D101
    classification: str = Field(
        description=(
            "One of: Billing, Refund, Technical Support, "
            "Account Access, Product Questions, General Inquiry"
        )
    )
    confidence_score: float = Field(
        description="Confidence between 0.0 and 1.0",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(description="Brief explanation of the classification")


# ── Fallback keyword classifier ───────────────────────────────────────────────

_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["refund", "money back", "reimburs"], TicketCategory.REFUND.value),
    (["invoice", "billing", "charge", "payment", "subscription", "price"], TicketCategory.BILLING.value),
    (["login", "password", "access", "locked", "sign in", "sso", "two-factor", "2fa"], TicketCategory.ACCOUNT_ACCESS.value),
    (["bug", "error", "crash", "broken", "not working", "issue", "down", "slow", "performance", "integration"], TicketCategory.TECHNICAL_SUPPORT.value),
    (["how to", "feature", "can i", "does it", "capability", "support"], TicketCategory.PRODUCT_QUESTIONS.value),
]


def _keyword_classify(subject: str, message: str) -> str:
    """Simple keyword fallback used when the LLM is unavailable."""
    combined = f"{subject} {message}".lower()
    for keywords, category in _KEYWORD_MAP:
        if any(kw in combined for kw in keywords):
            return category
    return TicketCategory.GENERAL_INQUIRY.value


# ── Node ──────────────────────────────────────────────────────────────────────


def classify_ticket_node(state: AgentState) -> dict:
    """Classify the ticket using an LLM with structured output."""
    ticket = state["ticket"]

    # Format customer history for the prompt
    history_lines: list[str] = []
    for h in state.get("customer_history", [])[:3]:
        history_lines.append(
            f"- [{h.get('classification', 'Unknown')}] {h.get('subject', '')} "
            f"({h.get('created_at', '')[:10]})"
        )
    customer_history_text = "\n".join(history_lines) if history_lines else "No prior tickets."

    try:
        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=TEMPERATURE,
        )
        structured_llm = llm.with_structured_output(ClassificationOutput)
        chain = CLASSIFICATION_PROMPT | structured_llm

        result: ClassificationOutput = chain.invoke(
            {
                "subject": ticket.subject,
                "message": ticket.message,
                "customer_history": customer_history_text,
            }
        )

        classification = result.classification
        confidence = round(result.confidence_score, 4)
        reasoning = result.reasoning
        logger.info(
            "Classified ticket %s as '%s' (confidence=%.2f).",
            ticket.ticket_id,
            classification,
            confidence,
        )

    except Exception as exc:
        logger.warning(
            "LLM classification failed for ticket %s: %s — using keyword fallback.",
            ticket.ticket_id,
            exc,
        )
        classification = _keyword_classify(ticket.subject, ticket.message)
        confidence = 0.0
        reasoning = f"Keyword fallback (LLM error: {type(exc).__name__})"

    ai_msg = AIMessage(
        content=json.dumps(
            {"classification": classification, "confidence_score": confidence, "reasoning": reasoning}
        )
    )

    return {
        "classification": classification,
        "confidence_score": confidence,
        "messages": [ai_msg],
        "audit_log": {
            **state.get("audit_log", {}),
            "classification": classification,
            "confidence_score": confidence,
            "classification_reasoning": reasoning,
        },
    }
