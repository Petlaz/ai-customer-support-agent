"""retrieve_policy_tool — LangChain tool that retrieves relevant policy chunks.

Embeds the query and returns the top-N matching chunks from the
policy_documents ChromaDB collection, formatted as a single context string.
"""
import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from rag.context_formatter import format_context
from rag.retriever import retrieve_policy_chunks

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class RetrievePolicyInput(BaseModel):
    query: str = Field(..., description="Search query text")
    n_results: int = Field(default=5, description="Number of policy chunks to retrieve", ge=1, le=20)


class RetrievePolicyOutput(BaseModel):
    policy_text: str = Field(description="Formatted policy context for the LLM prompt")
    chunks_retrieved: int = Field(description="Number of raw chunks returned by ChromaDB")


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def retrieve_policy(
    query: str,
    n_results: int = 5,
) -> dict:
    """Retrieve the most relevant company policy chunks for a given query.

    Returns formatted policy text and the number of chunks retrieved.
    Returns empty text if the policy collection is empty or unavailable.
    """
    try:
        results = retrieve_policy_chunks(query, n_results)
        policy_text = format_context(results) or ""
        logger.info("retrieve_policy: %d chunks for query '%s'.", len(results), query[:80])
        return RetrievePolicyOutput(
            policy_text=policy_text,
            chunks_retrieved=len(results),
        ).model_dump()
    except Exception as exc:
        logger.error("retrieve_policy failed: %s", exc)
        return RetrievePolicyOutput(policy_text="", chunks_retrieved=0).model_dump()
