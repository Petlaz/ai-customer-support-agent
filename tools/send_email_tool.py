"""send_email_tool — LangChain tool that sends a support response email.

Mock implementation: logs the email and returns a success response with a
fake message ID.  Replace the ``_send`` function body with real SMTP or
SendGrid/SES calls when an email provider is configured.
"""
import logging
import uuid
from datetime import datetime, timezone

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class SendEmailInput(BaseModel):
    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Plain-text email body")
    ticket_id: str = Field(..., description="Associated ticket ID for audit purposes")


class SendEmailOutput(BaseModel):
    sent: bool
    message_id: str
    sent_at: str


# ── Tool ────────────────────────────────────────────────────────────────────


@tool
def send_email(
    to_email: str,
    subject: str,
    body: str,
    ticket_id: str,
) -> dict:
    """Send a support response email to a customer.

    ⚠ Mock implementation — logs the email without delivering it.
    Replace this with SMTP / SES / SendGrid for production.
    """
    message_id = f"msg-{uuid.uuid4().hex[:12]}"
    sent_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        "[MOCK] send_email: ticket=%s to=%s subject='%s' message_id=%s",
        ticket_id,
        to_email,
        subject[:60],
        message_id,
    )
    return SendEmailOutput(sent=True, message_id=message_id, sent_at=sent_at).model_dump()
