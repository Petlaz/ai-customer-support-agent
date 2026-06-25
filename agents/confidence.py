"""Confidence scoring and escalation gate logic.

Three public functions used by the check_confidence node:

  - check_escalation_keywords(text)  → (bool, str)   forced-escalation keyword scan
  - meets_threshold(score)           → bool           compare to settings threshold
  - should_escalate(state)           → bool           combined gate used in the graph
"""
import logging

from config.constants import ESCALATION_KEYWORDS
from config.settings import settings

logger = logging.getLogger(__name__)


def check_escalation_keywords(text: str) -> tuple[bool, str]:
    """Scan text for escalation trigger keywords.

    Args:
        text: Combined ticket subject + message body.

    Returns:
        (True, matched_keyword) if a keyword is found, else (False, "").
    """
    lower = text.lower()
    for keyword in ESCALATION_KEYWORDS:
        if keyword in lower:
            logger.warning("Escalation keyword detected: '%s'", keyword)
            return True, keyword
    return False, ""


def meets_threshold(score: float) -> bool:
    """Return True when the confidence score meets the configured threshold."""
    return score >= settings.confidence_threshold


def should_escalate(state: dict) -> bool:
    """Combined escalation gate.

    Escalates when either:
      1. The confidence score is below settings.confidence_threshold, OR
      2. The ticket message contains a forced-escalation keyword.

    Args:
        state: Any dict containing 'ticket' and 'confidence_score' keys.

    Returns:
        True if the ticket should be escalated to a human agent.
    """
    ticket = state.get("ticket")
    combined_text = ""
    if ticket is not None:
        subject = getattr(ticket, "subject", "") or ""
        message = getattr(ticket, "message", "") or ""
        combined_text = f"{subject} {message}"

    keyword_trigger, _ = check_escalation_keywords(combined_text)
    if keyword_trigger:
        return True

    confidence = float(state.get("confidence_score", 0.0))
    if not meets_threshold(confidence):
        logger.info(
            "Confidence %.2f below threshold %.2f — escalating.",
            confidence,
            settings.confidence_threshold,
        )
        return True

    return False
