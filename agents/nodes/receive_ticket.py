"""receive_ticket node — graph entry point.

Validates the incoming TicketInput and initialises the AgentState fields
that later nodes will populate.  Appends a HumanMessage to the messages
list so the full conversation thread is preserved for auditing.

Creates the Langfuse trace for the entire ticket run so every subsequent
node can link its generations and spans to a single trace ID.
"""
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage

from agents.state import AgentState
from observability.langfuse_client import create_trace

logger = logging.getLogger(__name__)


def receive_ticket_node(state: AgentState) -> dict:
    """Validate the ticket, initialise default state values, and start the Langfuse trace."""
    ticket = state["ticket"]

    logger.info(
        "Receiving ticket %s from customer %s — channel=%s priority=%s",
        ticket.ticket_id,
        ticket.customer_id,
        ticket.channel,
        ticket.priority,
    )

    # Create Langfuse trace for the full workflow run (no-op if not configured)
    trace_id = create_trace(ticket.ticket_id, ticket.customer_id, ticket.subject) or ""

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
        "langfuse_trace_id": trace_id,
        "messages": [human_msg],
    }
