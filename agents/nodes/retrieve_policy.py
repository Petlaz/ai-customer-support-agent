"""retrieve_policy node — fetches relevant policy chunks from ChromaDB.

Builds a search query from the ticket classification + subject + message
and retrieves the top-N policy document chunks.  The raw chunk texts are
stored in state["retrieved_policies"] for the draft_response node.
"""
import logging

from agents.state import AgentState
from rag.context_formatter import format_context
from rag.retriever import retrieve_policy_chunks

logger = logging.getLogger(__name__)


def retrieve_policy_node(state: AgentState) -> dict:
    """Retrieve the most relevant policy chunks for the current ticket."""
    ticket = state["ticket"]
    classification = state.get("classification", "")

    # Combine classification + ticket text for a richer embedding query
    query = f"{classification} {ticket.subject} {ticket.message}"

    try:
        results = retrieve_policy_chunks(query)
        formatted = format_context(results)
        policy_chunks = [formatted] if formatted else []
    except Exception as exc:
        logger.warning("Policy retrieval failed for ticket %s: %s", ticket.ticket_id, exc)
        policy_chunks = []

    logger.info(
        "Retrieved %d policy chunk(s) for ticket %s (classification='%s').",
        len(results) if "results" in dir() else 0,
        ticket.ticket_id,
        classification,
    )

    return {
        "retrieved_policies": policy_chunks,
        "audit_log": {
            **state.get("audit_log", {}),
            "policy_chunks_retrieved": len(policy_chunks),
        },
    }
