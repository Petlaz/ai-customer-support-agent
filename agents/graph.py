"""LangGraph agent workflow — wires all nodes into a stateful StateGraph.

Graph topology
──────────────
receive_ticket
  └─► retrieve_long_term_memory
        └─► retrieve_semantic_memory
              └─► classify_ticket
                    └─► retrieve_policy
                          └─► draft_response
                                └─► [check_confidence]
                                      ├─ "route"    ─► route_ticket
                                      └─ "escalate" ─► escalate_ticket
                                                            ↓ (both paths merge)
                                                      summarize_ticket
                                                            └─► store_memory
                                                                  └─► log_decision
                                                                        └─► END

Usage
─────
    from agents.graph import graph

    result = graph.invoke({"ticket": ticket_input})
    # result is the final AgentState dict
"""
import logging

from langgraph.graph import END, StateGraph

from agents.nodes.check_confidence import check_confidence_node
from agents.nodes.classify_ticket import classify_ticket_node
from agents.nodes.draft_response import draft_response_node
from agents.nodes.escalate_ticket import escalate_ticket_node
from agents.nodes.log_decision import log_decision_node
from agents.nodes.receive_ticket import receive_ticket_node
from agents.nodes.retrieve_long_term_memory import retrieve_long_term_memory_node
from agents.nodes.retrieve_policy import retrieve_policy_node
from agents.nodes.retrieve_semantic_memory import retrieve_semantic_memory_node
from agents.nodes.route_ticket import route_ticket_node
from agents.nodes.store_memory import store_memory_node
from agents.nodes.summarize_ticket import summarize_ticket_node
from agents.state import AgentState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph StateGraph.

    Returns the compiled graph ready for invocation.
    """
    builder = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("receive_ticket", receive_ticket_node)
    builder.add_node("retrieve_long_term_memory", retrieve_long_term_memory_node)
    builder.add_node("retrieve_semantic_memory", retrieve_semantic_memory_node)
    builder.add_node("classify_ticket", classify_ticket_node)
    builder.add_node("retrieve_policy", retrieve_policy_node)
    builder.add_node("draft_response", draft_response_node)
    builder.add_node("route_ticket", route_ticket_node)
    builder.add_node("escalate_ticket", escalate_ticket_node)
    builder.add_node("summarize_ticket", summarize_ticket_node)
    builder.add_node("store_memory", store_memory_node)
    builder.add_node("log_decision", log_decision_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    builder.set_entry_point("receive_ticket")

    # ── Linear edges ─────────────────────────────────────────────────────────
    builder.add_edge("receive_ticket", "retrieve_long_term_memory")
    builder.add_edge("retrieve_long_term_memory", "retrieve_semantic_memory")
    builder.add_edge("retrieve_semantic_memory", "classify_ticket")
    builder.add_edge("classify_ticket", "retrieve_policy")
    builder.add_edge("retrieve_policy", "draft_response")

    # ── Conditional edge: check_confidence ───────────────────────────────────
    # check_confidence_node is a condition function (returns a string key).
    # LangGraph calls it after draft_response and routes accordingly.
    builder.add_conditional_edges(
        "draft_response",
        check_confidence_node,
        {
            "route": "route_ticket",
            "escalate": "escalate_ticket",
        },
    )

    # ── Merge paths → summarize ───────────────────────────────────────────────
    builder.add_edge("route_ticket", "summarize_ticket")
    builder.add_edge("escalate_ticket", "summarize_ticket")

    # ── Tail edges ────────────────────────────────────────────────────────────
    builder.add_edge("summarize_ticket", "store_memory")
    builder.add_edge("store_memory", "log_decision")
    builder.add_edge("log_decision", END)

    return builder.compile()


# Module-level compiled graph — import and call graph.invoke(state)
graph = build_graph()

logger.debug("LangGraph agent graph compiled successfully.")
