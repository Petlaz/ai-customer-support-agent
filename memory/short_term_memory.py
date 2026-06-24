"""Short-term memory — accessor helpers for in-flight AgentState fields.

Short-term memory lives entirely in LangGraph's AgentState TypedDict.
There is no database or external storage — data is scoped to a single
ticket processing run and discarded when the graph execution ends.

These helpers provide a clean, named API so agent nodes do not access
state dict keys directly.
"""
from agents.state import AgentState
from api.schemas.ticket_schema import TicketInput


# ── Readers ───────────────────────────────────────────────────────────────────


def get_ticket(state: AgentState) -> TicketInput:
    """Return the current ticket being processed."""
    return state["ticket"]


def get_classification(state: AgentState) -> str:
    """Return the current classification string (empty if not yet set)."""
    return state.get("classification", "")


def get_confidence(state: AgentState) -> float:
    """Return the current confidence score (0.0 if not yet set)."""
    return state.get("confidence_score", 0.0)


def get_retrieved_policies(state: AgentState) -> list[str]:
    """Return the list of retrieved policy chunks."""
    return state.get("retrieved_policies", [])


def get_draft_response(state: AgentState) -> str:
    """Return the current draft response (empty if not yet generated)."""
    return state.get("draft_response", "")


def get_routing_decision(state: AgentState) -> str:
    """Return the current routing department (empty if not yet decided)."""
    return state.get("routing_decision", "")


def is_escalated(state: AgentState) -> bool:
    """Return True if the ticket has been flagged for escalation."""
    return state.get("escalation_required", False)


def get_escalation_reason(state: AgentState) -> str:
    """Return the escalation reason string (empty if not escalated)."""
    return state.get("escalation_reason", "")


def get_similar_cases(state: AgentState) -> list[dict]:
    """Return similar historical cases retrieved from semantic memory."""
    return state.get("similar_cases", [])


def get_customer_history(state: AgentState) -> list[dict]:
    """Return the customer's prior ticket history loaded from long-term memory."""
    return state.get("customer_history", [])


# ── Partial state update builders ─────────────────────────────────────────────
# Each returns a dict that can be returned directly from a LangGraph node.


def set_classification(classification: str, confidence: float) -> dict:
    """Build a partial state update for classification results."""
    return {"classification": classification, "confidence_score": confidence}


def set_draft_response(response: str) -> dict:
    """Build a partial state update for the generated draft response."""
    return {"draft_response": response}


def set_routing_decision(department: str) -> dict:
    """Build a partial state update for the routing decision."""
    return {"routing_decision": department}


def set_escalation(reason: str) -> dict:
    """Build a partial state update marking the ticket as escalated."""
    return {"escalation_required": True, "escalation_reason": reason}


def set_memory_context(customer_history: list[dict], similar_cases: list[dict]) -> dict:
    """Build a partial state update for retrieved memory context."""
    return {"customer_history": customer_history, "similar_cases": similar_cases}
