"""Confidence scoring and escalation gate logic.

Public API
----------
check_escalation_keywords(text)     → (bool, keyword)   forced-keyword scan
check_missing_policy(state)         → (bool, reason)    no policy docs retrieved
check_high_value_refund(text)       → (bool, reason)    amount ≥ threshold
check_sensitive_data(text)          → (bool, reason)    PII pattern detected
check_ambiguous_request(state)      → (bool, reason)    message too vague / short
meets_threshold(score)              → bool              compare to settings threshold
determine_escalation_reason(state)  → (bool, reason)    evaluates ALL triggers
should_escalate(state)              → bool              thin wrapper for graph edge
"""
import logging
import re

from config.constants import (
    AMBIGUOUS_MESSAGE_WORD_THRESHOLD,
    ESCALATION_KEYWORDS,
    HIGH_VALUE_REFUND_THRESHOLD,
    TicketCategory,
)
from config.settings import settings

logger = logging.getLogger(__name__)

# ── Compiled regex patterns ────────────────────────────────────────────────────

# Matches 16-digit card numbers in groups of 4 (space or dash separated)
_CREDIT_CARD_RE = re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b")
# Standard US SSN format
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# Dollar amounts with optional thousands comma: $1,234.56 or $500
_MONEY_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")

# Refund-context keywords — high-value detection only applies when these appear
_REFUND_CONTEXT = frozenset(
    {"refund", "charge", "charged", "billing", "payment", "amount", "fee", "cost", "price", "paid"}
)


# ── Individual trigger functions ───────────────────────────────────────────────


def check_escalation_keywords(text: str) -> tuple[bool, str]:
    """Scan text for forced-escalation keywords (legal, compliance, fraud, etc.).

    Returns:
        (True, matched_keyword) if a keyword is found, else (False, "").
    """
    lower = text.lower()
    for keyword in ESCALATION_KEYWORDS:
        if keyword in lower:
            logger.warning("Escalation keyword detected: '%s'", keyword)
            return True, keyword
    return False, ""


def check_missing_policy(state: dict) -> tuple[bool, str]:
    """Escalate when no policy documents were retrieved for a non-general inquiry.

    General Inquiry tickets do not require policy context, so they are exempt.
    Tickets that have not yet been classified (empty string) are also exempt —
    this check only applies after the classify_ticket node has run.

    Returns:
        (True, reason) if policy docs are absent and ticket is not General Inquiry.
    """
    classification = state.get("classification", "")
    # Not classified yet or General Inquiry — no policy required
    if not classification or classification == TicketCategory.GENERAL_INQUIRY.value:
        return False, ""
    policies = state.get("retrieved_policies", [])
    if not policies:
        reason = "No relevant policy information found — human review required"
        logger.info("check_missing_policy: triggered for classification '%s'.", classification)
        return True, reason
    return False, ""


def check_high_value_refund(text: str, threshold: float = HIGH_VALUE_REFUND_THRESHOLD) -> tuple[bool, str]:
    """Detect monetary amounts above *threshold* in a refund or billing context.

    Only triggers when at least one refund-context keyword is present alongside
    the amount, to avoid false-positives on unrelated number mentions.

    Returns:
        (True, reason) if a qualifying amount is found, else (False, "").
    """
    lower = text.lower()
    if not any(kw in lower for kw in _REFUND_CONTEXT):
        return False, ""
    for match in _MONEY_RE.finditer(text):
        amount_str = match.group(1).replace(",", "")
        try:
            amount = float(amount_str)
            if amount >= threshold:
                reason = f"High-value amount detected: ${amount:,.2f} (threshold ${threshold:,.2f})"
                logger.warning("check_high_value_refund: %s", reason)
                return True, reason
        except ValueError:
            continue
    return False, ""


def check_sensitive_data(text: str) -> tuple[bool, str]:
    """Detect PII patterns (credit card numbers, SSNs) that require human review.

    Returns:
        (True, reason) if PII is detected, else (False, "").
    """
    if _CREDIT_CARD_RE.search(text):
        reason = "Potential credit card number detected in message"
        logger.warning("check_sensitive_data: credit card pattern found.")
        return True, reason
    if _SSN_RE.search(text):
        reason = "Potential SSN detected in message"
        logger.warning("check_sensitive_data: SSN pattern found.")
        return True, reason
    return False, ""


def check_ambiguous_request(state: dict) -> tuple[bool, str]:
    """Escalate when the message is too short or vague to process automatically.

    Triggers when:
      - The message word count is below AMBIGUOUS_MESSAGE_WORD_THRESHOLD, OR
      - confidence_score == 0.0 (LLM fell back to keyword classifier entirely).

    Returns:
        (True, reason) if the request appears ambiguous, else (False, "").
    """
    ticket = state.get("ticket")
    if ticket is not None:
        message = getattr(ticket, "message", "") or ""
        word_count = len(message.split())
        if word_count < AMBIGUOUS_MESSAGE_WORD_THRESHOLD:
            reason = (
                f"Message too short to process automatically ({word_count} words — "
                f"minimum {AMBIGUOUS_MESSAGE_WORD_THRESHOLD})"
            )
            logger.info("check_ambiguous_request: %s", reason)
            return True, reason

    confidence = float(state.get("confidence_score", 0.0))
    if confidence == 0.0:
        reason = "Classification confidence is 0.0 — LLM unavailable or request is unclear"
        logger.info("check_ambiguous_request: %s", reason)
        return True, reason

    return False, ""


# ── Threshold helper ───────────────────────────────────────────────────────────


def meets_threshold(score: float) -> bool:
    """Return True when *score* meets the configured confidence threshold."""
    return score >= settings.confidence_threshold


# ── Master escalation gate ─────────────────────────────────────────────────────


def determine_escalation_reason(state: dict) -> tuple[bool, str]:
    """Evaluate all escalation triggers in priority order.

    Priority (highest → lowest):
      1. Escalation keyword (legal, fraud, GDPR, …)
      2. Sensitive PII detected
      3. High-value refund / charge amount
      4. Ambiguous / unclear request
      5. Missing policy information
      6. Low confidence score

    Returns:
        (True, reason_string) if any trigger fires, else (False, "").
    """
    ticket = state.get("ticket")
    combined_text = ""
    if ticket is not None:
        subject = getattr(ticket, "subject", "") or ""
        message = getattr(ticket, "message", "") or ""
        combined_text = f"{subject} {message}"

    # 1. Forced-escalation keyword
    triggered, keyword = check_escalation_keywords(combined_text)
    if triggered:
        return True, f"Escalation keyword detected: '{keyword}'"

    # 2. Sensitive / PII data
    triggered, reason = check_sensitive_data(combined_text)
    if triggered:
        return True, reason

    # 3. High-value refund
    triggered, reason = check_high_value_refund(combined_text)
    if triggered:
        return True, reason

    # 4. Ambiguous / unclear request
    triggered, reason = check_ambiguous_request(state)
    if triggered:
        return True, reason

    # 5. Missing policy information
    triggered, reason = check_missing_policy(state)
    if triggered:
        return True, reason

    # 6. Low confidence score
    confidence = float(state.get("confidence_score", 0.0))
    if not meets_threshold(confidence):
        reason = (
            f"Low confidence score {confidence:.2f} "
            f"(threshold {settings.confidence_threshold:.2f})"
        )
        logger.info("determine_escalation_reason: %s", reason)
        return True, reason

    return False, ""


def should_escalate(state: dict) -> bool:
    """Return True if the ticket should be escalated to a human agent.

    Thin wrapper around :func:`determine_escalation_reason` for use as a
    LangGraph conditional-edge function.
    """
    escalate, _ = determine_escalation_reason(state)
    return escalate

