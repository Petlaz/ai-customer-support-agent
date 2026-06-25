"""check_confidence node — routing gate.

This node does NOT return state updates; it is used exclusively as the
condition function for a LangGraph conditional edge.  It examines the
current AgentState and returns the string key that selects the next node:

  "route"    → ticket is handled automatically (high confidence, no keywords)
  "escalate" → ticket is handed off to a human agent
"""
import logging

from agents.confidence import should_escalate
from agents.state import AgentState

logger = logging.getLogger(__name__)


def check_confidence_node(state: AgentState) -> str:
    """Conditional edge function: returns 'route' or 'escalate'.

    LangGraph calls this after the draft_response node and uses the
    returned string to select the next node in the graph.
    """
    if should_escalate(state):
        logger.info(
            "Ticket %s → ESCALATE (confidence=%.2f)",
            state["ticket"].ticket_id,
            state.get("confidence_score", 0.0),
        )
        return "escalate"

    logger.info(
        "Ticket %s → ROUTE (confidence=%.2f)",
        state["ticket"].ticket_id,
        state.get("confidence_score", 0.0),
    )
    return "route"
