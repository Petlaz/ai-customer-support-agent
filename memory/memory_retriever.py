"""Unified memory retrieval — combines long-term DB history and semantic similarity.

This is the read-side entry point called at the start of each agent run.
It returns a single MemoryContext containing everything the agent needs
to know about the customer and similar past tickets before it starts
classifying or drafting a response.
"""
import logging

from sqlalchemy.orm import Session

from api.schemas.memory_schema import MemoryContext, SimilarCase
from api.schemas.ticket_schema import TicketInput
from memory.customer_history import get_customer_history
from memory.semantic_memory import retrieve_similar

logger = logging.getLogger(__name__)


def retrieve_memory_context(
    db: Session,
    ticket: TicketInput,
) -> MemoryContext:
    """Return a MemoryContext for the given ticket.

    Fetches in parallel (logically):
    1. Customer's prior ticket history + escalation/refund counts (SQLite)
    2. Semantically similar historical tickets (ChromaDB TICKETS_COLLECTION)

    The similarity score is derived from ChromaDB's distance:
        similarity = 1 / (1 + distance)   — range [0, 1], higher = more similar
    """
    # ── Long-term: customer history from SQLite ───────────────────────────────
    customer_history = get_customer_history(db, ticket.customer_id)

    # ── Semantic: similar past tickets from ChromaDB ──────────────────────────
    query = f"{ticket.subject} {ticket.message}"
    raw_results = retrieve_similar(query)

    similar_cases: list[SimilarCase] = []
    for result in raw_results:
        meta = result.get("metadata", {})
        distance = result.get("distance", 1.0)
        similarity = round(1.0 / (1.0 + float(distance)), 4)

        similar_cases.append(
            SimilarCase(
                ticket_id=meta.get("ticket_id", "unknown"),
                subject=meta.get("subject", ""),
                message=result.get("document", ""),
                classification=meta.get("classification", ""),
                resolution=meta.get("resolution", ""),
                similarity_score=similarity,
            )
        )

    logger.info(
        "Memory context for ticket %s: %d prior tickets, %d similar cases.",
        ticket.ticket_id,
        customer_history.total_tickets,
        len(similar_cases),
    )

    return MemoryContext(
        customer_history=customer_history,
        similar_cases=similar_cases,
    )
