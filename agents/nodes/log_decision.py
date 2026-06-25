"""log_decision node — finalises the Langfuse trace at the end of the workflow.

The trace was created by receive_ticket at the start of the run.
LLM spans (classify, draft, summarize) were added automatically via
CallbackHandlers in each node.  Retrieval spans were added by
retrieve_policy and retrieve_semantic_memory.

This node adds the final routing/escalation span and updates the trace
with the complete agent output, token totals, and cost.

If Langfuse credentials are missing or the call fails the node logs a
warning and continues without raising — observability must not block the
agent pipeline.
"""
import logging

from agents.state import AgentState
from observability.langfuse_client import add_retrieval_span, update_trace

logger = logging.getLogger(__name__)


def log_decision_node(state: AgentState) -> dict:
    """Finalise the Langfuse trace with agent decision and cost data."""
    ticket = state["ticket"]
    trace_id = state.get("langfuse_trace_id") or None
    audit = state.get("audit_log", {})

    # Add routing/escalation decision span
    add_retrieval_span(
        trace_id,
        "route_or_escalate",
        query="",
        results=[
            {
                "routing_decision": state.get("routing_decision", ""),
                "escalation_required": state.get("escalation_required", False),
                "escalation_reason": state.get("escalation_reason", ""),
                "confidence_score": state.get("confidence_score", 0.0),
            }
        ],
    )

    # Update trace output + metadata (adds token totals, cost, summary)
    update_trace(
        trace_id,
        output={
            "classification": state.get("classification", ""),
            "confidence_score": state.get("confidence_score", 0.0),
            "routing_decision": state.get("routing_decision", ""),
            "escalation_required": state.get("escalation_required", False),
            "escalation_reason": state.get("escalation_reason", ""),
            "summary": state.get("summary", ""),
            "total_tokens": audit.get("total_tokens", 0),
            "total_cost_usd": audit.get("total_cost_usd", 0.0),
        },
        metadata=audit,
    )

    logger.info("Logged decision for ticket %s (trace_id=%s).", ticket.ticket_id, trace_id or "none")
    return {}

