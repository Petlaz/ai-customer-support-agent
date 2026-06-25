"""classify_ticket_tool — LangChain tool that classifies a support ticket.

Wraps the same ChatOpenAI structured-output chain used by the agent node,
with a keyword-based fallback when the LLM is unavailable.
"""
import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agents.nodes.classify_ticket import ClassificationOutput, _keyword_classify
from agents.prompts import CLASSIFICATION_PROMPT
from config.constants import TEMPERATURE
from config.settings import settings

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class ClassifyTicketInput(BaseModel):
    subject: str = Field(..., description="Ticket subject line")
    message: str = Field(..., description="Full customer message body")
    customer_history: str = Field(
        default="",
        description="Optional summary of the customer's prior ticket history",
    )


class ClassifyTicketOutput(BaseModel):
    classification: str = Field(description="Ticket category")
    confidence_score: float = Field(description="Confidence score 0.0–1.0")
    reasoning: str = Field(description="Brief explanation of the classification")


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def classify_ticket(
    subject: str,
    message: str,
    customer_history: str = "",
) -> dict:
    """Classify a support ticket into a category with a confidence score.

    Returns a dict with classification, confidence_score, and reasoning.
    Falls back to keyword matching when the LLM is unavailable.
    """
    history_text = customer_history or "No prior tickets."
    try:
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=TEMPERATURE,
        )
        structured_llm = llm.with_structured_output(ClassificationOutput)
        chain = CLASSIFICATION_PROMPT | structured_llm
        result: ClassificationOutput = chain.invoke(
            {"subject": subject, "message": message, "customer_history": history_text}
        )
        logger.info("classify_ticket: '%s' (%.2f)", result.classification, result.confidence_score)
        return ClassifyTicketOutput(
            classification=result.classification,
            confidence_score=round(result.confidence_score, 4),
            reasoning=result.reasoning,
        ).model_dump()

    except Exception as exc:
        logger.warning("classify_ticket LLM failed: %s — keyword fallback.", exc)
        return ClassifyTicketOutput(
            classification=_keyword_classify(subject, message),
            confidence_score=0.0,
            reasoning=f"Keyword fallback ({type(exc).__name__})",
        ).model_dump()
