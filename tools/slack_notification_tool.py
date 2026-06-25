"""slack_notification_tool — LangChain tool that sends a Slack alert.

Mock implementation: logs the notification without posting to Slack.
Replace with a real Slack Web API call (slack_sdk) when a bot token is
configured in settings.
"""
import logging
from datetime import datetime, timezone

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class SlackNotificationInput(BaseModel):
    channel: str = Field(..., description="Slack channel name, e.g. '#escalations'")
    message: str = Field(..., description="Notification message body")
    ticket_id: str = Field(..., description="Associated support ticket ID")
    escalation_reason: str = Field(default="", description="Why the ticket was escalated")


class SlackNotificationOutput(BaseModel):
    sent: bool
    channel: str
    timestamp: str


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def slack_notification(
    channel: str,
    message: str,
    ticket_id: str,
    escalation_reason: str = "",
) -> dict:
    """Send a Slack notification for an escalated or high-priority ticket.

    ⚠ Mock implementation — logs the notification without posting to Slack.
    Configure SLACK_BOT_TOKEN in settings and replace this with slack_sdk.
    """
    ts = datetime.now(timezone.utc).isoformat()
    logger.info(
        "[MOCK] slack_notification: channel=%s ticket=%s reason='%s'",
        channel,
        ticket_id,
        escalation_reason[:80],
    )
    return SlackNotificationOutput(sent=True, channel=channel, timestamp=ts).model_dump()
