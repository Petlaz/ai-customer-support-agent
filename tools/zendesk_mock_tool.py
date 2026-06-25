"""zendesk_mock_tool — LangChain tool that creates a Zendesk support ticket.

Mock implementation: generates a fake Zendesk ticket ID and URL.
Replace with a real Zendesk REST API call (zenpy or requests) when
Zendesk credentials are configured in settings.
"""
import logging
import random
from datetime import datetime, timezone

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class ZendeskCreateTicketInput(BaseModel):
    subject: str = Field(..., description="Zendesk ticket subject")
    description: str = Field(..., description="Full ticket description")
    customer_id: str = Field(..., description="Customer identifier (used as requester)")
    priority: str = Field(default="normal", description="Zendesk priority: urgent, high, normal, low")
    ticket_id: str = Field(..., description="Internal support ticket ID for cross-reference")


class ZendeskCreateTicketOutput(BaseModel):
    zendesk_id: str
    url: str
    created: bool
    created_at: str


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def create_zendesk_ticket(
    subject: str,
    description: str,
    customer_id: str,
    priority: str = "normal",
    ticket_id: str = "",
) -> dict:
    """Create a Zendesk ticket for an escalated customer support issue.

    ⚠ Mock implementation — returns a fake Zendesk ticket ID and URL.
    Configure ZENDESK_SUBDOMAIN and ZENDESK_API_TOKEN in settings for production.
    """
    zendesk_id = str(random.randint(100_000, 999_999))
    url = f"https://nexus.zendesk.com/tickets/{zendesk_id}"
    created_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        "[MOCK] create_zendesk_ticket: id=%s for ticket=%s customer=%s priority=%s",
        zendesk_id,
        ticket_id,
        customer_id,
        priority,
    )
    return ZendeskCreateTicketOutput(
        zendesk_id=zendesk_id,
        url=url,
        created=True,
        created_at=created_at,
    ).model_dump()
