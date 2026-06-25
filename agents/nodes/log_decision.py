"""log_decision node — sends the completed agent run to Langfuse.

Creates a Langfuse trace for the full ticket run and attaches spans for:
  - classification result
  - policy retrieval
  - draft response generation
  - routing / escalation decision

If Langfuse credentials are missing or the call fails the node logs a
warning and continues without raising — observability must not block the
agent pipeline.
"""
import logging

from agents.state import AgentState
from config.settings import settings

logger = logging.getLogger(__name__)


def _has_langfuse_config() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def log_decision_node(state: AgentState) -> dict:
    """Send the completed ticket run to Langfuse as a trace."""
    ticket = state["ticket"]
    trace_id = state.get("langfuse_trace_id", "") or None

    if not _has_langfuse_config():
        logger.debug("Langfuse not configured — skipping trace for ticket %s.", ticket.ticket_id)
        return {}

    try:
        from langfuse import Langfuse  # noqa: PLC0415  (lazy import)

        lf = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

        trace = lf.trace(
            id=trace_id,
            name="customer-support-agent",
            user_id=ticket.customer_id,
            session_id=ticket.ticket_id,
            input={
                "ticket_id": ticket.ticket_id,
                "subject": ticket.subject,
                "message": ticket.message[:500],
                "channel": str(ticket.channel),
                "priority": str(ticket.priority),
            },
            output={
                "classification": state.get("classification", ""),
                "confidence_score": state.get("confidence_score", 0.0),
                "routing_decision": state.get("routing_decision", ""),
                "escalation_required": state.get("escalation_required", False),
                "escalation_reason": state.get("escalation_reason", ""),
                "summary": state.get("summary", ""),
            },
            metadata=state.get("audit_log", {}),
        )

        # Span: classification
        trace.span(
            name="classify_ticket",
            input={"subject": ticket.subject, "message": ticket.message[:200]},
            output={
                "classification": state.get("classification", ""),
                "confidence_score": state.get("confidence_score", 0.0),
                "reasoning": state.get("audit_log", {}).get("classification_reasoning", ""),
            },
        )

        # Span: policy retrieval
        trace.span(
            name="retrieve_policy",
            input={"classification": state.get("classification", "")},
            output={"chunks_retrieved": len(state.get("retrieved_policies", []))},
        )

        # Span: draft response
        trace.span(
            name="draft_response",
            output={"response_length": len(state.get("draft_response", ""))},
        )

        # Span: routing decision
        trace.span(
            name="route_or_escalate",
            output={
                "routing_decision": state.get("routing_decision", ""),
                "escalation_required": state.get("escalation_required", False),
            },
        )

        lf.flush()
        resolved_trace_id = trace.id
        logger.info("Langfuse trace created for ticket %s: %s", ticket.ticket_id, resolved_trace_id)

        return {
            "langfuse_trace_id": resolved_trace_id,
            "audit_log": {
                **state.get("audit_log", {}),
                "langfuse_trace_id": resolved_trace_id,
            },
        }

    except Exception as exc:
        logger.warning(
            "Langfuse logging failed for ticket %s: %s", ticket.ticket_id, exc
        )
        return {}
