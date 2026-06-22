"""Pydantic schemas for escalation payloads sent to human reviewers."""
from pydantic import BaseModel, Field


class EscalationPayload(BaseModel):
    ticket_id: str
    customer_id: str
    reason: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    classification: str
    customer_history: list[dict] = Field(default_factory=list)
    similar_cases: list[dict] = Field(default_factory=list)
    retrieved_policies: list[str] = Field(default_factory=list)
    draft_response: str
    priority: str = "high"


class EscalationRequest(BaseModel):
    ticket_id: str
    reason: str
    confidence_score: float
