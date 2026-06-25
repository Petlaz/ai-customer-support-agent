"""Shared Langfuse helpers used by all agent nodes.

Every public function in this module is a guaranteed no-op when Langfuse
credentials are not configured, so nodes never need to guard against
missing config themselves.

Usage pattern in agent nodes
─────────────────────────────
    from observability.langfuse_client import (
        create_trace,
        get_callback_handler,
        add_retrieval_span,
        update_trace,
    )

    # receive_ticket node
    trace_id = create_trace(ticket_id, customer_id, subject)

    # LLM-calling nodes (classify, draft, summarize)
    handler = get_callback_handler(state.get("langfuse_trace_id"))
    callbacks = [handler] if handler else []
    result = chain.invoke(inputs, config={"callbacks": callbacks})

    # retrieval nodes (retrieve_policy, retrieve_semantic_memory)
    add_retrieval_span(trace_id, "retrieve_policy", query, results)

    # log_decision node (final)
    update_trace(trace_id, output={...}, metadata={...})
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# GPT-4o-mini pricing (per token).  Used by draft_response / summarize nodes
# to estimate cost from response_metadata.
_GPT4O_MINI_INPUT_COST_PER_TOKEN = 0.000_000_150   # $0.150 / 1M
_GPT4O_MINI_OUTPUT_COST_PER_TOKEN = 0.000_000_600  # $0.600 / 1M


def _has_config() -> bool:
    """Return True only when both Langfuse keys are present in settings."""
    from config.settings import settings  # noqa: PLC0415  (lazy import)
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def _make_client():  # type: ignore[return]
    """Return a Langfuse client, or raise if unavailable."""
    from langfuse import Langfuse  # noqa: PLC0415
    from config.settings import settings  # noqa: PLC0415
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


# ── Public helpers ─────────────────────────────────────────────────────────────


def create_trace(
    ticket_id: str,
    customer_id: str,
    subject: str,
) -> Optional[str]:
    """Create a new Langfuse trace at the start of a ticket run.

    Returns the trace ID (str) so it can be stored in ``AgentState`` and
    threaded through every subsequent node.  Returns ``None`` when Langfuse
    is not configured or the call fails.
    """
    if not _has_config():
        return None
    try:
        lf = _make_client()
        trace = lf.trace(
            name="customer-support-ticket",
            user_id=customer_id,
            session_id=ticket_id,
            input={"ticket_id": ticket_id, "subject": subject},
            metadata={"customer_id": customer_id, "ticket_id": ticket_id},
        )
        lf.flush()
        trace_id = str(trace.id)
        logger.debug("Created Langfuse trace %s for ticket %s.", trace_id, ticket_id)
        return trace_id
    except Exception as exc:
        logger.warning("Failed to create Langfuse trace for ticket %s: %s", ticket_id, exc)
        return None


def get_callback_handler(
    trace_id: Optional[str] = None,
) -> Any | None:
    """Return a LangChain ``CallbackHandler`` linked to *trace_id*.

    Pass the returned handler to ``chain.invoke`` via the ``callbacks`` key::

        handler = get_callback_handler(state["langfuse_trace_id"])
        callbacks = [handler] if handler else []
        result = chain.invoke(inputs, config={"callbacks": callbacks})

    The handler automatically records the prompt, completion, model name,
    token usage, latency, and cost for every LLM call.
    Returns ``None`` when Langfuse is not configured or the import fails.
    """
    if not _has_config():
        return None
    try:
        from langfuse.callback import CallbackHandler  # noqa: PLC0415
        from config.settings import settings  # noqa: PLC0415
        kwargs: dict[str, Any] = dict(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        if trace_id:
            kwargs["trace_id"] = trace_id
        return CallbackHandler(**kwargs)
    except Exception as exc:
        logger.warning("Failed to create Langfuse callback handler: %s", exc)
        return None


def add_retrieval_span(
    trace_id: Optional[str],
    span_name: str,
    query: str,
    results: list[dict],
) -> None:
    """Create a span on an existing trace for a retrieval step.

    Args:
        trace_id:  The ID of the Langfuse trace to attach the span to.
        span_name: Human-readable name, e.g. ``"retrieve_policy"``.
        query:     The embedding query text.
        results:   Raw results returned by the retriever (dicts).
    """
    if not _has_config() or not trace_id:
        return
    try:
        lf = _make_client()
        trace = lf.trace(id=trace_id)
        span = trace.span(
            name=span_name,
            input={"query": query[:300]},
            output={
                "num_results": len(results),
                "results": [
                    {
                        "id": r.get("id", ""),
                        "document": r.get("document", "")[:200],
                        "metadata": r.get("metadata", {}),
                        "distance": r.get("distance"),
                        "similarity_score": r.get("similarity_score"),
                    }
                    for r in results[:5]
                ],
            },
        )
        span.end()
        lf.flush()
    except Exception as exc:
        logger.warning("Failed to add Langfuse span '%s': %s", span_name, exc)


def update_trace(
    trace_id: Optional[str],
    output: dict,
    metadata: dict,
) -> None:
    """Update an existing trace with the final agent output and audit metadata.

    Called by ``log_decision`` at the end of the workflow.
    """
    if not _has_config() or not trace_id:
        return
    try:
        lf = _make_client()
        lf.trace(id=trace_id, output=output, metadata=metadata)
        lf.flush()
        logger.debug("Updated Langfuse trace %s.", trace_id)
    except Exception as exc:
        logger.warning("Failed to update Langfuse trace %s: %s", trace_id, exc)


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost in USD for a GPT-4o-mini call."""
    return round(
        prompt_tokens * _GPT4O_MINI_INPUT_COST_PER_TOKEN
        + completion_tokens * _GPT4O_MINI_OUTPUT_COST_PER_TOKEN,
        8,
    )
