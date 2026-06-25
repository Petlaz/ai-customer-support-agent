"""escalate_ticket node — packages the ticket for human review.

Determines the escalation reason (low confidence or keyword trigger),
sets escalation_required=True, and routes to the human review queue.
"""
import logging

from agents.confidence import check_escalation_keywords, meets_threshold
from agents.state import AgentState
from config.constants import Department

logger = logging.getLogger(__name__)


def escalate_ticket_node(state: AgentState) -> dict:
    """Build escalation payload and mark the ticket for human review."""
    ticket = state["ticket"]
    confidence = float(state.get("confidence_score", 0.0))

    # Determine escalation reason
    combined_text = f"{ticket.subject} {ticket.message}"
    keyword_triggered, matched_keyword = check_escalation_keywords(combined_text)

    if keyword_triggered:
        reason = f"Escalation keyword detected: '{matched_keyword}'"
    elif not meets_threshold(confidence):
        reason = (
            f"Low confidence score {confidence:.2f} "
            f"(threshold {__import__('config.settings', fromlist=['settings']).settings.confidence_threshold:.2f})"
        )
    else:
        reason = "Manual escalation triggered by agent logic"

    logger.warning(
        "Ticket %s ESCALATED — %s",
        ticket.ticket_id,
        reason,
    )

    return {
        "escalation_required": True,
        "escalation_reason": reason,
        "routing_decision": Department.HUMAN_REVIEW_QUEUE.value,
        "audit_log": {
            **state.get("audit_log", {}),
            "escalation_required": True,
            "escalation_reason": reason,
            "routing_decision": Department.HUMAN_REVIEW_QUEUE.value,
        },
    }
