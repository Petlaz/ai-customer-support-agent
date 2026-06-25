"""draft_response_tool — LangChain tool that drafts a customer-facing response.

Calls GPT-4o-mini with DRAFT_RESPONSE_PROMPT using the provided policy
context and customer history.  Falls back to a static template when the
LLM is unavailable.
"""
import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agents.nodes.draft_response import _extract_token_usage
from agents.prompts import DRAFT_RESPONSE_PROMPT
from config.constants import TEMPERATURE
from config.settings import settings
from observability.langfuse_client import estimate_cost

logger = logging.getLogger(__name__)

_FALLBACK_DRAFT = (
    "Thank you for contacting Nexus Software Support. "
    "A member of our team will review your request and respond shortly."
)


# ── Schemas ──────────────────────────────────────────────────────────────────

class DraftResponseInput(BaseModel):
    subject: str = Field(..., description="Ticket subject")
    message: str = Field(..., description="Customer message")
    classification: str = Field(..., description="Ticket category")
    policy_context: str = Field(default="", description="Relevant policy text")
    similar_cases: str = Field(default="", description="Resolved similar cases summary")
    customer_history: str = Field(default="", description="Customer's prior ticket summary")


class DraftResponseOutput(BaseModel):
    draft: str = Field(description="Customer-facing response text")
    tokens_used: int = Field(default=0)
    cost_usd: float = Field(default=0.0)


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def draft_response(
    subject: str,
    message: str,
    classification: str,
    policy_context: str = "",
    similar_cases: str = "",
    customer_history: str = "",
) -> dict:
    """Draft a professional customer-facing response using relevant policy context.

    Returns the draft text, token count, and estimated cost in USD.
    Falls back to a generic template when the LLM is unavailable.
    """
    prompt_tokens = completion_tokens = 0
    try:
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=TEMPERATURE,
        )
        chain = DRAFT_RESPONSE_PROMPT | llm
        response = chain.invoke(
            {
                "classification": classification,
                "subject": subject,
                "message": message,
                "policy_context": policy_context or "No policy documents available.",
                "similar_cases": similar_cases or "No similar resolved cases.",
                "customer_history": customer_history or "No prior interactions.",
            }
        )
        draft = response.content.strip()
        prompt_tokens, completion_tokens = _extract_token_usage(response)
        logger.info("draft_response: %d chars, %d tokens.", len(draft), prompt_tokens + completion_tokens)

    except Exception as exc:
        logger.warning("draft_response LLM failed: %s — fallback.", exc)
        draft = _FALLBACK_DRAFT

    return DraftResponseOutput(
        draft=draft,
        tokens_used=prompt_tokens + completion_tokens,
        cost_usd=estimate_cost(prompt_tokens, completion_tokens),
    ).model_dump()
