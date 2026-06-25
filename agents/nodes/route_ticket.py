"""route_ticket node — assigns the ticket to the appropriate department.

Looks up the classification in CATEGORY_TO_DEPARTMENT and writes the
result into state["routing_decision"].  This is the happy-path branch;
escalated tickets go through escalate_ticket instead.
"""
import logging

from config.constants import CATEGORY_TO_DEPARTMENT, Department
from agents.state import AgentState

logger = logging.getLogger(__name__)


def route_ticket_node(state: AgentState) -> dict:
    """Map ticket classification to a handling department."""
    classification = state.get("classification", "")

    department = CATEGORY_TO_DEPARTMENT.get(
        classification,
        Department.CUSTOMER_SUCCESS_TEAM,
    )

    logger.info(
        "Ticket %s classified as '%s' → routed to '%s'.",
        state["ticket"].ticket_id,
        classification,
        department.value,
    )

    return {
        "routing_decision": department.value,
        "escalation_required": False,
        "audit_log": {
            **state.get("audit_log", {}),
            "routing_decision": department.value,
            "escalation_required": False,
        },
    }
