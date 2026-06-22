from datetime import datetime

from pydantic import BaseModel, Field


class EvalCase(BaseModel):
    case_id: str
    ticket_input: dict
    expected_classification: str
    expected_routing: str
    expected_escalation: bool
    notes: str | None = None


class EvalResult(BaseModel):
    case_id: str
    ticket_id: str
    actual_classification: str
    expected_classification: str
    classification_correct: bool
    actual_routing: str
    expected_routing: str
    routing_correct: bool
    actual_escalation: bool
    expected_escalation: bool
    escalation_correct: bool
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: int
    tokens_used: int
    cost_usd: float
    langfuse_trace_id: str | None = None
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
