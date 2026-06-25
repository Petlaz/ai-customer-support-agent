"""retrieve_similar_cases_tool — LangChain tool for semantic ticket retrieval.

Embeds the query and searches the historical_tickets ChromaDB collection
to surface the most relevant previously resolved cases.
"""
import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from memory.semantic_memory import retrieve_similar

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class RetrieveSimilarCasesInput(BaseModel):
    query: str = Field(..., description="Ticket text to find similar cases for")
    n_results: int = Field(default=3, description="Max similar cases to return", ge=1, le=10)


class RetrieveSimilarCasesOutput(BaseModel):
    similar_cases: list[dict] = Field(default_factory=list)
    count: int = Field(description="Number of cases returned")


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def retrieve_similar_cases(
    query: str,
    n_results: int = 3,
) -> dict:
    """Retrieve historically similar resolved support tickets by semantic similarity.

    Returns a list of similar cases with ticket_id, subject, classification,
    resolution, and similarity_score.
    """
    try:
        raw_results = retrieve_similar(query, n_results)
        cases = []
        for result in raw_results:
            meta = result.get("metadata", {})
            distance = result.get("distance", 1.0)
            similarity = round(1.0 / (1.0 + float(distance)), 4)
            cases.append(
                {
                    "ticket_id": meta.get("ticket_id", "unknown"),
                    "subject": meta.get("subject", ""),
                    "classification": meta.get("classification", ""),
                    "resolution": meta.get("resolution", ""),
                    "similarity_score": similarity,
                }
            )
        logger.info("retrieve_similar_cases: %d results for query '%s'.", len(cases), query[:80])
        return RetrieveSimilarCasesOutput(similar_cases=cases, count=len(cases)).model_dump()
    except Exception as exc:
        logger.error("retrieve_similar_cases failed: %s", exc)
        return RetrieveSimilarCasesOutput(similar_cases=[], count=0).model_dump()
