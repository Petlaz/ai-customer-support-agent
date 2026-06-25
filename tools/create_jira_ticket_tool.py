"""create_jira_ticket_tool — LangChain tool that creates a Jira ticket.

Mock implementation: generates a fake Jira ticket ID and URL.
Replace with a real Jira REST API call (atlassian-python-api or requests)
when Jira credentials are configured in settings.
"""
import logging
import random
from datetime import datetime, timezone

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class CreateJiraTicketInput(BaseModel):
    title: str = Field(..., description="Jira issue title / summary")
    description: str = Field(..., description="Full issue description")
    priority: str = Field(default="Medium", description="Jira priority: Highest, High, Medium, Low, Lowest")
    ticket_id: str = Field(..., description="Support ticket ID for cross-reference")
    customer_id: str = Field(..., description="Customer identifier")


class CreateJiraTicketOutput(BaseModel):
    jira_ticket_id: str
    url: str
    created: bool
    created_at: str


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def create_jira_ticket(
    title: str,
    description: str,
    priority: str = "Medium",
    ticket_id: str = "",
    customer_id: str = "",
) -> dict:
    """Create a Jira issue for an escalated support ticket.

    ⚠ Mock implementation — returns a fake Jira ticket ID and URL.
    Replace with a real Jira REST API call for production.
    """
    jira_id = f"SUP-{random.randint(1000, 9999)}"
    url = f"https://nexus.atlassian.net/browse/{jira_id}"
    created_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        "[MOCK] create_jira_ticket: %s for ticket=%s customer=%s",
        jira_id,
        ticket_id,
        customer_id,
    )
    return CreateJiraTicketOutput(
        jira_ticket_id=jira_id,
        url=url,
        created=True,
        created_at=created_at,
    ).model_dump()
