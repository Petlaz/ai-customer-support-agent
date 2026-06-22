import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage

from api.schemas.ticket_schema import TicketInput


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────────
    ticket: TicketInput

    # ── Memory retrieval results ───────────────────────────────────────────────
    customer_history: list[dict]        # from long-term memory (PostgreSQL)
    similar_cases: list[dict]           # from semantic memory (ChromaDB)

    # ── Classification ─────────────────────────────────────────────────────────
    classification: str                 # TicketCategory value
    confidence_score: float             # 0.0 – 1.0

    # ── RAG results ────────────────────────────────────────────────────────────
    retrieved_policies: list[str]       # relevant policy chunks

    # ── Generation ─────────────────────────────────────────────────────────────
    draft_response: str

    # ── Routing & Escalation ───────────────────────────────────────────────────
    routing_decision: str               # Department value
    escalation_required: bool
    escalation_reason: str

    # ── Output ─────────────────────────────────────────────────────────────────
    summary: str
    audit_log: dict
    langfuse_trace_id: str

    # ── Conversation messages (accumulated across nodes) ───────────────────────
    messages: Annotated[list[BaseMessage], operator.add]
