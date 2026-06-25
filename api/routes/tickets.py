"""Ticket endpoints.

POST /tickets/analyze   — run the full LangGraph agent on a ticket
POST /tickets/classify  — classify a ticket without drafting a response
POST /tickets/respond   — draft a response for a pre-classified ticket
POST /tickets/route     — map a classification to a department
POST /tickets/history   — retrieve a customer’s prior ticket history
GET  /tickets/{ticket_id} — fetch a ticket record by ID
"""
import time
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.schemas.ticket_schema import TicketInput, TicketResponse
from database.models import Customer, Ticket
from database.session import get_db
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request bodies for lightweight endpoints ────────────────────────────────

class RespondRequest(BaseModel):
    subject: str
    message: str
    classification: str
    policy_context: str = ""
    similar_cases: str = ""
    customer_history: str = ""


class RouteRequest(BaseModel):
    classification: str


class HistoryRequest(BaseModel):
    customer_id: str
    limit: int = 10


# ── Helpers ─────────────────────────────────────────────────────────────────


def _initial_state(ticket: TicketInput) -> dict:
    """Build the empty AgentState dict required by graph.invoke()."""
    return {
        "ticket": ticket,
        "customer_history": [],
        "similar_cases": [],
        "classification": "",
        "confidence_score": 0.0,
        "retrieved_policies": [],
        "draft_response": "",
        "routing_decision": "",
        "escalation_required": False,
        "escalation_reason": "",
        "escalation_payload": {},
        "summary": "",
        "audit_log": {},
        "langfuse_trace_id": "",
        "messages": [],
    }


def _trace_url(trace_id: str) -> str | None:
    if not trace_id:
        return None
    host = (settings.langfuse_host or "").rstrip("/")
    return f"{host}/traces/{trace_id}" if host else None


# ── POST /tickets/analyze ────────────────────────────────────────────────────


@router.post("/analyze", response_model=TicketResponse, summary="Run the full agent on a ticket")
def analyze_ticket(request: Request, ticket: TicketInput):
    """Run the full LangGraph agent pipeline and return a structured result.

    The graph runs synchronously: classify → retrieve → draft → route/escalate → summarise.
    """
    start_ms = int(time.time() * 1000)
    graph = request.app.state.graph
    logger.info("Analyzing ticket %s for customer %s", ticket.ticket_id, ticket.customer_id)

    result: dict = graph.invoke(_initial_state(ticket))

    elapsed = int(time.time() * 1000) - start_ms
    audit = result.get("audit_log") or {}
    trace_id = result.get("langfuse_trace_id") or ""

    return TicketResponse(
        ticket_id=ticket.ticket_id,
        classification=result.get("classification") or "",
        confidence_score=result.get("confidence_score") or 0.0,
        response=result.get("draft_response") or "",
        routing_decision=result.get("routing_decision") or "",
        escalated=result.get("escalation_required") or False,
        escalation_reason=result.get("escalation_reason") or None,
        summary=result.get("summary") or "",
        langfuse_trace_url=_trace_url(trace_id),
        processing_time_ms=elapsed,
        tokens_used=int(audit.get("total_tokens", 0)),
        cost_usd=float(audit.get("total_cost_usd", 0.0)),
    )


# ── POST /tickets/classify ──────────────────────────────────────────────────


@router.post("/classify", summary="Classify a ticket without drafting a response")
def classify_ticket_endpoint(ticket: TicketInput):
    """Classify a support ticket using GPT-4o-mini structured output.

    Faster than /analyze — skips retrieval, drafting, and memory writes.
    """
    from tools.classify_ticket_tool import classify_ticket  # noqa: PLC0415
    return classify_ticket.invoke({
        "subject": ticket.subject,
        "message": ticket.message,
        "customer_history": "",
    })


# ── POST /tickets/respond ───────────────────────────────────────────────────


@router.post("/respond", summary="Draft a customer response for a pre-classified ticket")
def respond_to_ticket(body: RespondRequest):
    """Draft a professional customer-facing response.

    Accepts pre-retrieved policy context and similar cases so the caller
    can control what context the model sees.
    """
    from tools.draft_response_tool import draft_response  # noqa: PLC0415
    return draft_response.invoke({
        "subject": body.subject,
        "message": body.message,
        "classification": body.classification,
        "policy_context": body.policy_context,
        "similar_cases": body.similar_cases,
        "customer_history": body.customer_history,
    })


# ── POST /tickets/route ─────────────────────────────────────────────────────


@router.post("/route", summary="Map a ticket classification to a department")
def route_ticket_endpoint(body: RouteRequest):
    """Return the department that handles the given ticket classification."""
    from tools.route_ticket_tool import route_ticket  # noqa: PLC0415
    return route_ticket.invoke({"classification": body.classification})


# ── POST /tickets/history ──────────────────────────────────────────────────


@router.post("/history", summary="Retrieve a customer’s prior ticket history")
def get_ticket_history(body: HistoryRequest, db: Session = Depends(get_db)):
    """Return the full ticket history for a customer from the database."""
    customer = db.query(Customer).filter_by(customer_id=body.customer_id).first()
    if not customer:
        return {
            "customer_id": body.customer_id,
            "tickets": [],
            "total_tickets": 0,
            "previous_escalations": 0,
        }
    tickets = (
        db.query(Ticket)
        .filter_by(customer_id=body.customer_id)
        .order_by(Ticket.created_at.desc())
        .limit(body.limit)
        .all()
    )
    escalations = sum(1 for t in tickets if t.status == "escalated")
    return {
        "customer_id": body.customer_id,
        "tickets": [
            {
                "ticket_id": t.ticket_id,
                "subject": t.subject,
                "classification": t.classification,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ],
        "total_tickets": len(tickets),
        "previous_escalations": escalations,
    }


# ── GET /tickets/{ticket_id} ────────────────────────────────────────────────


@router.get("/{ticket_id}", summary="Fetch a ticket record by ID")
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    """Return the stored ticket record for the given ticket_id."""
    ticket = db.query(Ticket).filter_by(ticket_id=ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found")
    return {
        "ticket_id": ticket.ticket_id,
        "customer_id": ticket.customer_id,
        "subject": ticket.subject,
        "classification": ticket.classification,
        "confidence_score": ticket.confidence_score,
        "status": ticket.status,
        "channel": ticket.channel,
        "priority": ticket.priority,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
    }
