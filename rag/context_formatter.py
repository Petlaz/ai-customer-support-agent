"""Formats retrieved document chunks into a clean context string for the LLM prompt."""

DEFAULT_SEPARATOR = "\n\n---\n\n"


def format_context(results: list[dict], max_chunks: int = 5) -> str:
    """Concatenate the top retrieved chunks into a single context string.

    Each chunk is prefixed with its source filename so the LLM knows
    which policy it is citing.
    """
    if not results:
        return "No relevant policy information found."

    parts = []
    for result in results[:max_chunks]:
        source = result.get("metadata", {}).get("source", "unknown")
        text = result.get("document", "").strip()
        parts.append(f"[Source: {source}]\n{text}")

    return DEFAULT_SEPARATOR.join(parts)


def format_similar_cases(results: list[dict], max_cases: int = 3) -> str:
    """Format historically similar ticket results for the LLM prompt."""
    if not results:
        return "No similar historical cases found."

    parts = []
    for result in results[:max_cases]:
        meta = result.get("metadata", {})
        text = result.get("document", "").strip()
        ticket_id = meta.get("ticket_id", "unknown")
        classification = meta.get("classification", "")
        parts.append(f"[Similar Case: {ticket_id} | {classification}]\n{text}")

    return DEFAULT_SEPARATOR.join(parts)
