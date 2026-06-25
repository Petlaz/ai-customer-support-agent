"""Unit tests for Phase 9 — Human-in-the-Loop escalation pipeline.

Covers all 7 escalation triggers in agents/confidence.py plus:
  - determine_escalation_reason (master gate)
  - should_escalate (LangGraph edge wrapper)
  - escalate_ticket_node (state output + EscalationPayload)
  - EscalationPayload / EscalationReview schema validation
"""

from unittest.mock import MagicMock, patch

import pytest

from agents.confidence import (
    check_ambiguous_request,
    check_escalation_keywords,
    check_high_value_refund,
    check_missing_policy,
    check_sensitive_data,
    determine_escalation_reason,
    meets_threshold,
    should_escalate,
)
from api.schemas.escalation_schema import (
    EscalationPayload,
    EscalationRequest,
    EscalationReview,
    EscalationTrigger,
)
from config.constants import (
    AMBIGUOUS_MESSAGE_WORD_THRESHOLD,
    HIGH_VALUE_REFUND_THRESHOLD,
    Department,
    TicketCategory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ticket(subject="Billing issue", message="I was charged twice for my subscription."):
    t = MagicMock()
    t.subject = subject
    t.message = message
    t.ticket_id = "T001"
    t.customer_id = "C001"
    return t


def _make_state(
    subject="Billing issue",
    message="I was charged twice for my subscription.",
    confidence=0.85,
    classification=TicketCategory.BILLING.value,
    retrieved_policies=None,
    customer_history=None,
    similar_cases=None,
    draft_response="Thank you for reaching out.",
):
    return {
        "ticket": _make_ticket(subject, message),
        "confidence_score": confidence,
        "classification": classification,
        "retrieved_policies": retrieved_policies if retrieved_policies is not None else ["Policy chunk 1"],
        "customer_history": customer_history or [],
        "similar_cases": similar_cases or [],
        "draft_response": draft_response,
        "audit_log": {},
    }


# ---------------------------------------------------------------------------
# Trigger 1 — Escalation keyword (legal / compliance / fraud)
# ---------------------------------------------------------------------------

class TestCheckEscalationKeywords:
    @pytest.mark.parametrize("keyword", [
        "legal", "lawsuit", "lawyer", "attorney", "court",
        "compliance", "fraud", "unauthorized charge", "data breach",
        "privacy violation", "gdpr", "threatening", "discrimination", "harassment",
    ])
    def test_detects_each_keyword(self, keyword):
        triggered, matched = check_escalation_keywords(f"I will take {keyword} action")
        assert triggered is True
        assert matched == keyword

    def test_case_insensitive(self):
        triggered, matched = check_escalation_keywords("I am consulting my LAWYER")
        assert triggered is True
        assert matched == "lawyer"

    def test_no_keyword_returns_false(self):
        triggered, matched = check_escalation_keywords("I need help with my invoice please")
        assert triggered is False
        assert matched == ""

    def test_empty_text_returns_false(self):
        triggered, _ = check_escalation_keywords("")
        assert triggered is False


# ---------------------------------------------------------------------------
# Trigger 2 — Missing policy information
# ---------------------------------------------------------------------------

class TestCheckMissingPolicy:
    def test_triggers_when_no_policies_and_non_general_inquiry(self):
        state = _make_state(
            classification=TicketCategory.BILLING.value,
            retrieved_policies=[],
            message="My invoice has an error that needs to be reviewed by your team.",
        )
        triggered, reason = check_missing_policy(state)
        assert triggered is True
        assert "policy" in reason.lower()

    def test_empty_classification_is_exempt(self):
        """Ticket not yet classified should not trigger missing-policy escalation."""
        state = _make_state(classification="", retrieved_policies=[])
        triggered, _ = check_missing_policy(state)
        assert triggered is False

    def test_general_inquiry_exempt(self):
        state = _make_state(
            classification=TicketCategory.GENERAL_INQUIRY.value,
            retrieved_policies=[],
        )
        triggered, _ = check_missing_policy(state)
        assert triggered is False

    def test_does_not_trigger_when_policies_present(self):
        state = _make_state(
            classification=TicketCategory.TECHNICAL_SUPPORT.value,
            retrieved_policies=["Use the reset link."],
        )
        triggered, _ = check_missing_policy(state)
        assert triggered is False

    @pytest.mark.parametrize("category", [
        TicketCategory.BILLING.value,
        TicketCategory.REFUND.value,
        TicketCategory.TECHNICAL_SUPPORT.value,
        TicketCategory.ACCOUNT_ACCESS.value,
        TicketCategory.PRODUCT_QUESTIONS.value,
    ])
    def test_all_non_general_categories_trigger_on_empty_policies(self, category):
        state = _make_state(classification=category, retrieved_policies=[])
        triggered, _ = check_missing_policy(state)
        assert triggered is True


# ---------------------------------------------------------------------------
# Trigger 3 — High-value refund / charge
# ---------------------------------------------------------------------------

class TestCheckHighValueRefund:
    def test_triggers_above_threshold(self):
        text = "I want a refund for the $750 charge on my account."
        triggered, reason = check_high_value_refund(text)
        assert triggered is True
        assert "$750" in reason or "750" in reason

    def test_does_not_trigger_below_threshold(self):
        text = "I need a refund for the $50 charge."
        triggered, _ = check_high_value_refund(text)
        assert triggered is False

    def test_triggers_at_exact_threshold(self):
        text = f"I was charged ${HIGH_VALUE_REFUND_THRESHOLD:.0f} and want a refund."
        triggered, _ = check_high_value_refund(text)
        assert triggered is True

    def test_ignores_large_amounts_without_refund_context(self):
        # No refund-context keyword — pure project discussion
        text = "The project has 1000 users and 500 servers deployed globally."
        triggered, _ = check_high_value_refund(text)
        assert triggered is False

    def test_handles_comma_formatted_amounts(self):
        text = "I need a refund for the $1,500.00 payment."
        triggered, reason = check_high_value_refund(text)
        assert triggered is True

    def test_custom_threshold(self):
        text = "I want a refund for the $200 charge."
        triggered, _ = check_high_value_refund(text, threshold=100.0)
        assert triggered is True

    def test_no_monetary_amount_returns_false(self):
        text = "I'd like a refund for my subscription please."
        triggered, _ = check_high_value_refund(text)
        assert triggered is False


# ---------------------------------------------------------------------------
# Trigger 4 — Sensitive / PII data
# ---------------------------------------------------------------------------

class TestCheckSensitiveData:
    def test_detects_credit_card_spaced(self):
        text = "My card number is 4111 1111 1111 1111 please verify."
        triggered, reason = check_sensitive_data(text)
        assert triggered is True
        assert "credit card" in reason.lower()

    def test_detects_credit_card_dashed(self):
        text = "Card: 4111-1111-1111-1111"
        triggered, reason = check_sensitive_data(text)
        assert triggered is True

    def test_detects_credit_card_no_separator(self):
        text = "My number is 4111111111111111."
        triggered, _ = check_sensitive_data(text)
        assert triggered is True

    def test_detects_ssn(self):
        text = "My SSN is 123-45-6789."
        triggered, reason = check_sensitive_data(text)
        assert triggered is True
        assert "ssn" in reason.lower()

    def test_no_pii_returns_false(self):
        text = "I need help resetting my password on the Nexus platform."
        triggered, _ = check_sensitive_data(text)
        assert triggered is False

    def test_empty_text_returns_false(self):
        triggered, _ = check_sensitive_data("")
        assert triggered is False


# ---------------------------------------------------------------------------
# Trigger 5 — Ambiguous / unclear request
# ---------------------------------------------------------------------------

class TestCheckAmbiguousRequest:
    def test_triggers_on_short_message(self):
        short_msg = "help please"  # 2 words < threshold
        state = _make_state(message=short_msg, confidence=0.9)
        triggered, reason = check_ambiguous_request(state)
        assert triggered is True
        assert "short" in reason.lower() or "words" in reason.lower()

    def test_triggers_on_zero_confidence(self):
        state = _make_state(confidence=0.0)
        triggered, reason = check_ambiguous_request(state)
        assert triggered is True
        assert "0.0" in reason or "unclear" in reason.lower()

    def test_does_not_trigger_on_sufficient_message(self):
        long_msg = "I have been having trouble logging into my account for the past three days."
        state = _make_state(message=long_msg, confidence=0.9)
        triggered, _ = check_ambiguous_request(state)
        assert triggered is False

    def test_threshold_boundary(self):
        # Exactly at threshold — should NOT trigger (threshold is strictly less-than)
        words = " ".join(["word"] * AMBIGUOUS_MESSAGE_WORD_THRESHOLD)
        state = _make_state(message=words, confidence=0.85)
        triggered, _ = check_ambiguous_request(state)
        assert triggered is False

    def test_one_below_threshold_triggers(self):
        words = " ".join(["word"] * (AMBIGUOUS_MESSAGE_WORD_THRESHOLD - 1))
        state = _make_state(message=words, confidence=0.85)
        triggered, _ = check_ambiguous_request(state)
        assert triggered is True


# ---------------------------------------------------------------------------
# Trigger 6 — Low confidence score
# ---------------------------------------------------------------------------

class TestMeetsThreshold:
    def test_above_threshold_passes(self):
        assert meets_threshold(0.9) is True

    def test_at_threshold_passes(self):
        from config.settings import settings
        assert meets_threshold(settings.confidence_threshold) is True

    def test_below_threshold_fails(self):
        assert meets_threshold(0.1) is False

    def test_zero_fails(self):
        assert meets_threshold(0.0) is False


# ---------------------------------------------------------------------------
# determine_escalation_reason — master gate
# ---------------------------------------------------------------------------

class TestDetermineEscalationReason:
    def test_keyword_trigger_takes_priority(self):
        """Keyword should fire before all other checks."""
        state = _make_state(
            message="I will take legal action for the $1000 refund.",
            confidence=0.9,
            retrieved_policies=["Policy text"],
        )
        triggered, reason = determine_escalation_reason(state)
        assert triggered is True
        assert "keyword" in reason.lower() or "legal" in reason.lower()

    def test_pii_trigger(self):
        state = _make_state(message="My SSN is 123-45-6789 please verify.")
        triggered, reason = determine_escalation_reason(state)
        assert triggered is True
        assert "ssn" in reason.lower() or "sensitive" in reason.lower() or "pii" in reason.lower()

    def test_high_value_trigger(self):
        state = _make_state(
            message="I need a refund for the $900 charge.",
            confidence=0.9,
            retrieved_policies=["Policy text"],
        )
        triggered, reason = determine_escalation_reason(state)
        assert triggered is True
        assert "$900" in reason or "900" in reason

    def test_missing_policy_trigger(self):
        state = _make_state(
            classification=TicketCategory.BILLING.value,
            retrieved_policies=[],
            confidence=0.9,
            message="My bill has an error that needs fixing right away.",
        )
        triggered, reason = determine_escalation_reason(state)
        assert triggered is True
        assert "policy" in reason.lower()

    def test_low_confidence_trigger(self):
        state = _make_state(confidence=0.3, retrieved_policies=["Policy text"])
        triggered, reason = determine_escalation_reason(state)
        assert triggered is True
        assert "confidence" in reason.lower() or "0.30" in reason

    def test_ambiguous_trigger(self):
        state = _make_state(message="hi", confidence=0.9, retrieved_policies=["Policy"])
        triggered, reason = determine_escalation_reason(state)
        assert triggered is True
        assert "short" in reason.lower() or "ambiguous" in reason.lower() or "words" in reason.lower()

    def test_no_trigger_clean_ticket(self):
        state = _make_state(
            message="I need help understanding my invoice from last month.",
            confidence=0.85,
            classification=TicketCategory.BILLING.value,
            retrieved_policies=["Billing policy text here"],
        )
        triggered, reason = determine_escalation_reason(state)
        assert triggered is False
        assert reason == ""


# ---------------------------------------------------------------------------
# should_escalate — LangGraph edge wrapper
# ---------------------------------------------------------------------------

class TestShouldEscalate:
    def test_returns_true_on_keyword(self):
        state = _make_state(message="I will take legal action.")
        assert should_escalate(state) is True

    def test_returns_true_on_low_confidence(self):
        state = _make_state(confidence=0.2, retrieved_policies=["Policy"])
        assert should_escalate(state) is True

    def test_returns_false_on_clean_ticket(self):
        state = _make_state(
            message="My invoice amount seems incorrect this month.",
            confidence=0.85,
            retrieved_policies=["Billing policy"],
        )
        assert should_escalate(state) is False


# ---------------------------------------------------------------------------
# escalate_ticket_node
# ---------------------------------------------------------------------------

class TestEscalateTicketNode:
    def test_sets_escalation_required_true(self):
        from agents.nodes.escalate_ticket import escalate_ticket_node

        state = _make_state(message="I will take legal action against your company.")
        result = escalate_ticket_node(state)

        assert result["escalation_required"] is True

    def test_routing_to_human_review_queue(self):
        from agents.nodes.escalate_ticket import escalate_ticket_node

        state = _make_state(confidence=0.2, retrieved_policies=["Policy"])
        result = escalate_ticket_node(state)

        assert result["routing_decision"] == Department.HUMAN_REVIEW_QUEUE.value

    def test_escalation_payload_is_dict(self):
        from agents.nodes.escalate_ticket import escalate_ticket_node

        state = _make_state(message="I will sue your company.")
        result = escalate_ticket_node(state)

        assert isinstance(result["escalation_payload"], dict)

    def test_escalation_payload_contains_required_fields(self):
        from agents.nodes.escalate_ticket import escalate_ticket_node

        state = _make_state(
            confidence=0.2,
            retrieved_policies=["Policy text"],
            customer_history=[{"ticket_id": "T0"}],
            similar_cases=[{"ticket_id": "T1"}],
        )
        result = escalate_ticket_node(state)
        payload = result["escalation_payload"]

        assert payload["ticket_id"] == "T001"
        assert payload["customer_id"] == "C001"
        assert isinstance(payload["customer_history"], list)
        assert isinstance(payload["similar_cases"], list)
        assert isinstance(payload["retrieved_policies"], list)
        assert "draft_response" in payload
        assert "confidence_score" in payload
        assert "reason" in payload

    def test_escalation_reason_in_audit_log(self):
        from agents.nodes.escalate_ticket import escalate_ticket_node

        state = _make_state(confidence=0.1, retrieved_policies=["Policy"])
        result = escalate_ticket_node(state)

        assert result["audit_log"]["escalation_required"] is True
        assert "escalation_reason" in result["audit_log"]

    def test_reason_reflects_keyword_trigger(self):
        from agents.nodes.escalate_ticket import escalate_ticket_node

        state = _make_state(message="This is harassment and I want legal action taken.")
        result = escalate_ticket_node(state)

        reason = result["escalation_reason"]
        assert "keyword" in reason.lower() or "harassment" in reason.lower() or "legal" in reason.lower()


# ---------------------------------------------------------------------------
# EscalationPayload schema
# ---------------------------------------------------------------------------

class TestEscalationPayloadSchema:
    def test_minimal_valid_payload(self):
        payload = EscalationPayload(
            ticket_id="T001",
            customer_id="C001",
            reason="Low confidence",
            confidence_score=0.3,
        )
        assert payload.priority == "high"
        assert isinstance(payload.created_at, str)
        assert payload.customer_history == []

    def test_full_payload_roundtrip(self):
        payload = EscalationPayload(
            ticket_id="T002",
            customer_id="C002",
            subject="Billing dispute",
            message="I was charged twice.",
            reason="High-value amount detected: $750.00",
            confidence_score=0.82,
            classification=TicketCategory.BILLING.value,
            customer_history=[{"ticket_id": "T0", "subject": "Prior issue"}],
            similar_cases=[{"ticket_id": "T1", "similarity_score": 0.9}],
            retrieved_policies=["Refunds processed within 5 business days."],
            draft_response="We're sorry to hear about this.",
        )
        data = payload.model_dump()
        restored = EscalationPayload(**data)
        assert restored.ticket_id == "T002"
        assert restored.confidence_score == 0.82

    def test_confidence_score_bounds(self):
        with pytest.raises(Exception):
            EscalationPayload(
                ticket_id="T", customer_id="C", reason="x", confidence_score=1.5
            )


# ---------------------------------------------------------------------------
# EscalationReview schema
# ---------------------------------------------------------------------------

class TestEscalationReviewSchema:
    def test_approve_draft_decision(self):
        review = EscalationReview(
            ticket_id="T001",
            reviewer_id="agent-42",
            decision="approve_draft",
        )
        assert review.final_response == ""
        assert isinstance(review.reviewed_at, str)

    def test_override_response_decision(self):
        review = EscalationReview(
            ticket_id="T002",
            reviewer_id="agent-07",
            decision="override_response",
            final_response="We have processed your refund.",
            notes="Customer confirmed via phone.",
        )
        assert review.notes == "Customer confirmed via phone."

    def test_all_valid_decisions(self):
        for decision in ("approve_draft", "override_response", "reassign", "close"):
            r = EscalationReview(ticket_id="T", reviewer_id="R", decision=decision)
            assert r.decision == decision


# ---------------------------------------------------------------------------
# EscalationTrigger enum
# ---------------------------------------------------------------------------

class TestEscalationTriggerEnum:
    def test_all_values_are_strings(self):
        for trigger in EscalationTrigger:
            assert isinstance(trigger.value, str)

    def test_expected_triggers_exist(self):
        values = {t.value for t in EscalationTrigger}
        expected = {
            "low_confidence", "keyword_match", "missing_policy",
            "high_value_refund", "sensitive_data", "ambiguous_request", "manual",
        }
        assert expected == values
