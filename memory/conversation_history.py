"""Manages the LangChain message history stored in AgentState and the conversations table.

LangChain messages (HumanMessage / AIMessage) flow through AgentState.messages
during a single run. This module provides helpers to build and format those
messages, and to persist them to the conversations table after the run.
"""
import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy.orm import Session

from database.models import Conversation

logger = logging.getLogger(__name__)


# ── Message builders ──────────────────────────────────────────────────────────


def build_human_message(text: str) -> HumanMessage:
    """Wrap a customer text string in a LangChain HumanMessage."""
    return HumanMessage(content=text)


def build_ai_message(text: str) -> AIMessage:
    """Wrap an agent response string in a LangChain AIMessage."""
    return AIMessage(content=text)


# ── Formatting ────────────────────────────────────────────────────────────────


def format_history(messages: list[BaseMessage]) -> str:
    """Return a human-readable conversation transcript from a list of messages.

    Each line is prefixed with "Customer:" or "Agent:" depending on message type.
    Returns an empty string if the message list is empty.
    """
    if not messages:
        return ""

    lines = []
    for msg in messages:
        role = "Customer" if isinstance(msg, HumanMessage) else "Agent"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def get_last_agent_message(messages: list[BaseMessage]) -> str:
    """Return the content of the most recent AIMessage, or empty string if none."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg.content
    return ""


# ── Persistence ───────────────────────────────────────────────────────────────


def save_messages_to_db(
    db: Session,
    ticket_id: str,
    customer_id: str,
    messages: list[BaseMessage],
) -> None:
    """Persist all conversation messages to the conversations table.

    Skips empty messages. Role is stored as "customer" or "agent".
    """
    if not messages:
        return

    rows = []
    for msg in messages:
        if not msg.content:
            continue
        role = "customer" if isinstance(msg, HumanMessage) else "agent"
        rows.append(
            Conversation(
                ticket_id=ticket_id,
                customer_id=customer_id,
                role=role,
                content=msg.content,
            )
        )

    if rows:
        db.add_all(rows)
        db.commit()
        logger.info(
            "Saved %d conversation messages for ticket %s.",
            len(rows),
            ticket_id,
        )
