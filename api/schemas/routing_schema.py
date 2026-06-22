"""Pydantic schemas for ticket routing decisions and routing requests."""
from pydantic import BaseModel, Field


class RoutingDecision(BaseModel):
    ticket_id: str
    department: str
    reason: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_escalation: bool = False


class RoutingRequest(BaseModel):
    ticket_id: str
    classification: str
    confidence_score: float
    customer_id: str
