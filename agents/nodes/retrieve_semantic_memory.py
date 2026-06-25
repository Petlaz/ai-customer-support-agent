"""retrieve_semantic_memory node — fetches similar past tickets from ChromaDB.

Embeds the incoming ticket text and queries the historical_tickets
collection to surface the most relevant resolved cases.  The results
are stored in state["similar_cases"] for later use by draft_response.

Langfuse: a retrieval span is added to the workflow trace recording the
query, similarity scores, and top-N case previews.
"""
import logging

from agents.state import AgentState
from memory.semantic_memory import retrieve_similar
from observability.langfuse_client import add_retrieval_span

logger = logging.getLogger(__name__)


def retrieve_semantic_memory_node(state: AgentState) -> dict:
    """Retrieve semantically similar historical tickets from ChromaDB."""
    ticket = state["ticket"]
    query = f"{ticket.subject} {ticket.message}"
    trace_id = state.get("langfuse_trace_id") or None

    raw_results: list[dict] = []
    try:
        raw_results = retrieve_similar(query)
    except Exception as exc:
        logger.warning("Semantic memory retrieval failed: %s", exc)

    similar_cases: list[dict] = []
    for result in raw_results:
        meta = result.get("metadata", {})
        distance = result.get("distance", 1.0)
        similarity = round(1.0 / (1.0 + float(distance)), 4)
        similar_cases.append(
            {
                "ticket_id": meta.get("ticket_id", "unknown"),
                "subject": meta.get("subject", ""),
                "message": result.get("document", ""),
                "classification": meta.get("classification", ""),
                "resolution": meta.get("resolution", ""),
                "similarity_score": similarity,
            }
        )

    # Langfuse span (no-op if not configured)
    add_retrieval_span(trace_id, "retrieve_semantic_memory", query, raw_results)

    logger.info("Retrieved %d similar cases for ticket %s.", len(similar_cases), ticket.ticket_id)

    return {
        "similar_cases": similar_cases,
        "audit_log": {
            **state.get("audit_log", {}),
            "similar_cases_found": len(similar_cases),
        },
    }



def retrieve_semantic_memory_node(state: AgentState) -> dict:
    """Retrieve semantically similar historical tickets from ChromaDB."""
    ticket = state["ticket"]
    query = f"{ticket.subject} {ticket.message}"

    try:
        raw_results = retrieve_similar(query)
    except Exception as exc:
        logger.warning("Semantic memory retrieval failed: %s", exc)
        raw_results = []

    similar_cases: list[dict] = []
    for result in raw_results:
        meta = result.get("metadata", {})
        distance = result.get("distance", 1.0)
        similarity = round(1.0 / (1.0 + float(distance)), 4)
        similar_cases.append(
            {
                "ticket_id": meta.get("ticket_id", "unknown"),
                "subject": meta.get("subject", ""),
                "message": result.get("document", ""),
                "classification": meta.get("classification", ""),
                "resolution": meta.get("resolution", ""),
                "similarity_score": similarity,
            }
        )

    logger.info("Retrieved %d similar cases for ticket %s.", len(similar_cases), ticket.ticket_id)

    return {
        "similar_cases": similar_cases,
        "audit_log": {
            **state.get("audit_log", {}),
            "similar_cases_found": len(similar_cases),
        },
    }
