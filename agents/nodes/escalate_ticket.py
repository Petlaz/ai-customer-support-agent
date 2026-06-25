"""escalate_ticket node — packages the ticket for human review.

Determines the escalation reason using the full trigger pipeline in
`agents.confidence`, sets escalation_required=True, routes to the human
review queue, and stores a complete EscalationPayload snapshot in state.
"""
import logging

from agents.confidence import determine_escalation_reason
from agents.state import AgentState
from api.schemas.escalation_schema import EscalationPayload
from config.constants import Department

logger = logging.getLogger(__name__)


def escalate_ticket_node(state: AgentState) -> dict:
    """Build a full EscalationPayload and mark the ticket for human review."""
    ticket = state["ticket"]

    # Use the full trigger pipeline to determine escalation reason
    _, reason = determine_escalation_reason(state)
    if not reason:
        reason = "Manual escalation triggered by agent logic"

    logger.warning(
        "Ticket %s ESCALATED — %s",
        ticket.ticket_id,
        reason,
    )

    # Build the structured payload the human reviewer will receive
    payload = EscalationPayload(
        ticket_id=ticket.ticket_id,
        customer_id=ticket.customer_id,
        subject=ticket.subject,
        message=ticket.message,
        reason=reason,
        confidence_score=float(state.get("confidence_score", 0.0)),
        classification=state.get("classification", ""),
        customer_history=state.get("customer_history", []),
        similar_cases=state.get("similar_cases", []),
        retrieved_policies=state.get("retrieved_policies", []),
        draft_response=state.get("draft_response", ""),
        priority="high",
    )

    return {
        "escalation_required": True,
        "escalation_reason": reason,
        "routing_decision": Department.HUMAN_REVIEW_QUEUE.value,
        "escalation_payload": payload.model_dump(),
        "audit_log": {
            **state.get("audit_log", {}),
            "escalation_required": True,
            "escalation_reason": reason,
            "routing_decision": Department.HUMAN_REVIEW_QUEUE.value,
        },
    }
