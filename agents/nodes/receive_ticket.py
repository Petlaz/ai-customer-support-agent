"""receive_ticket node — graph entry point.

Validates the incoming TicketInput and initialises the AgentState fields
that later nodes will populate.  Appends a HumanMessage to the messages
list so the full conversation thread is preserved for auditing.
"""
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage

from agents.state import AgentState

logger = logging.getLogger(__name__)


def receive_ticket_node(state: AgentState) -> dict:
    """Validate the ticket and initialise default state values.

    Returns a partial state dict that LangGraph merges into AgentState.
    """
    ticket = state["ticket"]

    logger.info(
        "Receiving ticket %s from customer %s — channel=%s priority=%s",
        ticket.ticket_id,
        ticket.customer_id,
        ticket.channel,
        ticket.priority,
    )

    human_msg = HumanMessage(
        content=f"Subject: {ticket.subject}\n\n{ticket.message}",
        additional_kwargs={"ticket_id": ticket.ticket_id},
    )

    return {
        "customer_history": [],
        "similar_cases": [],
        "classification": "",
        "confidence_score": 0.0,
        "retrieved_policies": [],
        "draft_response": "",
        "routing_decision": "",
        "escalation_required": False,
        "escalation_reason": "",
        "summary": "",
        "audit_log": {
            "ticket_id": ticket.ticket_id,
            "customer_id": ticket.customer_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
        },
        "langfuse_trace_id": "",
        "messages": [human_msg],
    }
