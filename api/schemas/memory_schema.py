from datetime import datetime

from pydantic import BaseModel, Field


class PreviousTicket(BaseModel):
    ticket_id: str
    subject: str
    classification: str
    resolution: str | None = None
    created_at: datetime


class CustomerHistory(BaseModel):
    customer_id: str
    tickets: list[PreviousTicket] = Field(default_factory=list)
    total_tickets: int = 0
    previous_escalations: int = 0
    previous_refunds: int = 0


class SimilarCase(BaseModel):
    ticket_id: str
    subject: str
    message: str
    classification: str
    resolution: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)


class MemoryContext(BaseModel):
    customer_history: CustomerHistory
    similar_cases: list[SimilarCase] = Field(default_factory=list)
