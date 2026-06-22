from datetime import datetime

from pydantic import BaseModel, Field

from config.constants import TicketChannel, TicketPriority


class TicketInput(BaseModel):
    ticket_id: str = Field(..., description="Unique ticket identifier")
    customer_id: str = Field(..., description="Customer identifier")
    subject: str = Field(..., description="Ticket subject line")
    message: str = Field(..., min_length=1, description="Full customer message")
    channel: TicketChannel = Field(default=TicketChannel.API, description="Submission channel")
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, description="Ticket priority")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Ticket creation timestamp")


class TicketResponse(BaseModel):
    ticket_id: str
    classification: str
    confidence_score: float
    response: str
    routing_decision: str
    escalated: bool
    escalation_reason: str | None = None
    summary: str
    langfuse_trace_url: str | None = None
    processing_time_ms: int
    tokens_used: int
    cost_usd: float
