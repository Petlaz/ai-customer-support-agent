"""retrieve_policy node — fetches relevant policy chunks from ChromaDB.

Builds a search query from the ticket classification + subject + message
and retrieves the top-N policy document chunks.  The raw chunk texts are
stored in state["retrieved_policies"] for the draft_response node.

Langfuse: a retrieval span is added to the workflow trace recording the
query, number of results, and top-N chunk previews.
"""
import logging

from agents.state import AgentState
from observability.langfuse_client import add_retrieval_span
from rag.context_formatter import format_context
from rag.retriever import retrieve_policy_chunks

logger = logging.getLogger(__name__)


def retrieve_policy_node(state: AgentState) -> dict:
    """Retrieve the most relevant policy chunks for the current ticket."""
    ticket = state["ticket"]
    classification = state.get("classification", "")
    trace_id = state.get("langfuse_trace_id") or None

    # Combine classification + ticket text for a richer embedding query
    query = f"{classification} {ticket.subject} {ticket.message}"

    results: list[dict] = []
    try:
        results = retrieve_policy_chunks(query)
        formatted = format_context(results)
        policy_chunks = [formatted] if formatted else []
    except Exception as exc:
        logger.warning("Policy retrieval failed for ticket %s: %s", ticket.ticket_id, exc)
        policy_chunks = []

    # Langfuse span (no-op if not configured)
    add_retrieval_span(trace_id, "retrieve_policy", query, results)

    logger.info(
        "Retrieved %d policy chunk(s) for ticket %s (classification='%s').",
        len(results),
        ticket.ticket_id,
        classification,
    )

    return {
        "retrieved_policies": policy_chunks,
        "audit_log": {
            **state.get("audit_log", {}),
            "policy_chunks_retrieved": len(results),
        },
    }
