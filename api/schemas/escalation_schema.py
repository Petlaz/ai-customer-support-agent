"""Pydantic schemas for escalation payloads sent to human reviewers."""
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EscalationTrigger(str, Enum):
    """Enum of all supported escalation trigger types."""
    LOW_CONFIDENCE = "low_confidence"
    KEYWORD_MATCH = "keyword_match"
    MISSING_POLICY = "missing_policy"
    HIGH_VALUE_REFUND = "high_value_refund"
    SENSITIVE_DATA = "sensitive_data"
    AMBIGUOUS_REQUEST = "ambiguous_request"
    MANUAL = "manual"


class EscalationPayload(BaseModel):
    """Full context package sent to the human reviewer for escalated tickets."""
    ticket_id: str
    customer_id: str
    subject: str = ""
    message: str = ""
    reason: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    classification: str = ""
    customer_history: list[dict] = Field(default_factory=list)
    similar_cases: list[dict] = Field(default_factory=list)
    retrieved_policies: list[str] = Field(default_factory=list)
    draft_response: str = ""
    priority: str = "high"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EscalationRequest(BaseModel):
    """Minimal escalation request — used internally when only IDs are available."""
    ticket_id: str
    reason: str
    confidence_score: float


class EscalationReview(BaseModel):
    """Human reviewer decision submitted via the API."""
    ticket_id: str
    reviewer_id: str = Field(..., description="ID of the human reviewer")
    decision: str = Field(
        ...,
        description="One of: 'approve_draft', 'override_response', 'reassign', 'close'",
    )
    final_response: str = Field(
        default="",
        description="The reviewer's final customer-facing response (if overriding the draft)",
    )
    notes: str = Field(
        default="",
        description="Internal notes from the reviewer",
    )
    reviewed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
