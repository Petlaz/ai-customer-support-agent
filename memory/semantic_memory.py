"""Semantic memory — indexes resolved ticket embeddings and retrieves similar past cases.

Wraps rag/vector_store.py for the TICKETS_COLLECTION. Resolved tickets are
embedded and stored so that incoming tickets can be matched against them by
semantic similarity, surfacing relevant historical resolutions for the LLM.
"""
import logging

from langchain_core.documents import Document

from config.settings import settings
from rag.vector_store import TICKETS_COLLECTION, add_documents, query_collection

logger = logging.getLogger(__name__)


def index_ticket(
    ticket_id: str,
    text: str,
    metadata: dict | None = None,
) -> None:
    """Embed a resolved ticket and upsert it into the tickets ChromaDB collection.

    Args:
        ticket_id: Unique ticket identifier — used as the stable document ID.
        text:      The text to embed (typically subject + message + resolution).
        metadata:  Optional extra fields (classification, subject, resolution, etc.)
                   stored alongside the embedding for filtering and display.
    """
    meta: dict = {
        "ticket_id": ticket_id,
        "chunk_index": 0,
        **(metadata or {}),
    }
    doc = Document(page_content=text, metadata=meta)
    count = add_documents([doc], collection_name=TICKETS_COLLECTION)
    logger.info("Indexed ticket %s in semantic memory (%d document).", ticket_id, count)


def index_tickets_batch(tickets: list[dict]) -> int:
    """Embed and upsert a batch of resolved tickets.

    Each dict must have: ticket_id (str), text (str).
    Optional keys are forwarded as ChromaDB metadata.

    Returns the total number of documents upserted.
    """
    if not tickets:
        return 0

    docs = []
    for i, t in enumerate(tickets):
        meta = {k: v for k, v in t.items() if k not in ("text",)}
        # Use ticket_id as source so add_documents generates unique ChromaDB IDs
        meta.setdefault("source", t.get("ticket_id", f"ticket_{i}"))
        meta.setdefault("chunk_index", 0)
        docs.append(Document(page_content=t["text"], metadata=meta))

    count = add_documents(docs, collection_name=TICKETS_COLLECTION)
    logger.info("Batch-indexed %d tickets into semantic memory.", count)
    return count


def retrieve_similar(
    query: str,
    n_results: int | None = None,
) -> list[dict]:
    """Retrieve the most semantically similar historical tickets for a query.

    Returns a list of result dicts: {document, metadata, distance, id}.
    Returns an empty list if the tickets collection is empty (no history yet).
    """
    n = n_results or settings.max_similar_cases
    results = query_collection(query, collection_name=TICKETS_COLLECTION, n_results=n)
    logger.info("Retrieved %d similar tickets for query: '%s'", len(results), query[:80])
    return results
