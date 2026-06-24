"""Retrieves the most relevant policy chunks from ChromaDB for a given query."""
import logging

from config.settings import settings
from rag.vector_store import POLICY_COLLECTION, TICKETS_COLLECTION, query_collection

logger = logging.getLogger(__name__)


def retrieve_policy_chunks(
    query: str,
    n_results: int | None = None,
) -> list[dict]:
    """Retrieve the top policy document chunks most relevant to the query."""
    n_results = n_results or settings.max_retrieval_docs
    results = query_collection(query, collection_name=POLICY_COLLECTION, n_results=n_results)
    logger.info("Retrieved %d policy chunks for query: '%s'", len(results), query[:80])
    return results


def retrieve_similar_tickets(
    query: str,
    n_results: int | None = None,
) -> list[dict]:
    """Retrieve historically similar tickets from the tickets collection."""
    n_results = n_results or settings.max_similar_cases
    results = query_collection(query, collection_name=TICKETS_COLLECTION, n_results=n_results)
    logger.info("Retrieved %d similar tickets for query: '%s'", len(results), query[:80])
    return results
