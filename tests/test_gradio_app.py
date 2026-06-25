"""Tests for frontend/gradio_app.py (Phase 12).

The analyze_ticket() function is tested with a mocked graph so no LLM
calls are made. The Gradio `demo` object is imported to verify the UI
builds without errors.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOCK_RESULT = {
    "classification": "Billing",
    "confidence_score": 0.92,
    "draft_response": "Thank you for contacting us. We will investigate the duplicate charge.",
    "routing_decision": "Billing Team",
    "escalation_required": False,
    "escalation_reason": "",
    "escalation_payload": {},
    "summary": "Customer reported a duplicate $49.99 charge; routed to Billing Team.",
    "langfuse_trace_id": "trace-demo-001",
    "audit_log": {"total_tokens": 280, "total_cost_usd": 0.00028},
    "retrieved_policies": ["Refunds are processed within 5-7 business days."],
    "customer_history": [
        {
            "ticket_id": "TKT-PREV-1",
            "subject": "Billing error",
            "classification": "Billing",
            "resolution": "resolved",
            "created_at": "2024-01-01T10:00:00",
        }
    ],
    "similar_cases": [
        {
            "ticket_id": "TKT-SIM-1",
            "document": "Duplicate billing charge",
            "classification": "Billing",
            "similarity": 0.87,
        }
    ],
    "messages": [],
}

_VALID_INPUTS = (
    "TKT-TEST-001",        # ticket_id
    "CUST-TEST-001",       # customer_id
    "Charged twice",       # subject
    "I see two charges.",  # message
    "email",               # channel
    "medium",              # priority
)


def _mock_graph():
    g = MagicMock()
    g.invoke.return_value = _MOCK_RESULT
    return g


# ---------------------------------------------------------------------------
# Import smoke test
# ---------------------------------------------------------------------------

class TestGradioAppImport:
    def test_demo_object_is_importable(self):
        """The demo Blocks object must be constructable without errors."""
        with patch("agents.graph.build_graph", return_value=_mock_graph()):
            import importlib
            import frontend.gradio_app as mod  # noqa: PLC0415
            importlib.reload(mod)
            assert mod.demo is not None

    def test_analyze_ticket_function_exists(self):
        from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
        assert callable(analyze_ticket)


# ---------------------------------------------------------------------------
# analyze_ticket() -- core logic
# ---------------------------------------------------------------------------

class TestAnalyzeTicketValidation:
    def test_empty_subject_returns_error(self):
        from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
        result = analyze_ticket("", "", "", "Some message", "email", "medium")
        assert "required" in result[0].lower()

    def test_empty_message_returns_error(self):
        from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
        result = analyze_ticket("", "", "Some subject", "", "email", "medium")
        assert "required" in result[0].lower()

    def test_returns_seven_outputs(self):
        from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
        with patch("frontend.gradio_app._get_graph", return_value=_mock_graph()):
            result = analyze_ticket(*_VALID_INPUTS)
        assert len(result) == 7


class TestAnalyzeTicketDecisionPanel:
    @pytest.fixture(autouse=True)
    def _patch_graph(self):
        with patch("frontend.gradio_app._get_graph", return_value=_mock_graph()):
            yield

    def _run(self):
        from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
        return analyze_ticket(*_VALID_INPUTS)

    def test_decision_contains_classification(self):
        decision, *_ = self._run()
        assert "Billing" in decision

    def test_decision_contains_routing(self):
        decision, *_ = self._run()
        assert "Billing Team" in decision

    def test_decision_not_escalated(self):
        decision, *_ = self._run()
        assert "NO" in decision  # badge text inside HTML span

    def test_decision_contains_ticket_id(self):
        decision, *_ = self._run()
        assert "TKT-TEST-001" in decision

    def test_decision_contains_confidence(self):
        decision, *_ = self._run()
        assert "92%" in decision  # rendered in HTML confidence bar


class TestAnalyzeTicketResponsePanel:
    def test_response_contains_draft(self):
        with patch("frontend.gradio_app._get_graph", return_value=_mock_graph()):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            _, response, *_ = analyze_ticket(*_VALID_INPUTS)
        assert "duplicate charge" in response.lower() or "billing" in response.lower()


class TestAnalyzeTicketPoliciesPanel:
    def test_policies_shows_chunk(self):
        with patch("frontend.gradio_app._get_graph", return_value=_mock_graph()):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            _, _, _, policies, *_ = analyze_ticket(*_VALID_INPUTS)
        assert "Policy chunk 1" in policies or "5-7 business days" in policies

    def test_no_policies_shows_placeholder(self):
        mock = _mock_graph()
        mock.invoke.return_value = {**_MOCK_RESULT, "retrieved_policies": []}
        with patch("frontend.gradio_app._get_graph", return_value=mock):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            _, _, _, policies, *_ = analyze_ticket(*_VALID_INPUTS)
        assert "No policy" in policies


class TestAnalyzeTicketMemoryPanel:
    def test_memory_shows_prior_ticket(self):
        with patch("frontend.gradio_app._get_graph", return_value=_mock_graph()):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            _, _, _, _, memory, *_ = analyze_ticket(*_VALID_INPUTS)
        assert "TKT-PREV-1" in memory

    def test_no_history_shows_placeholder(self):
        mock = _mock_graph()
        mock.invoke.return_value = {**_MOCK_RESULT, "customer_history": []}
        with patch("frontend.gradio_app._get_graph", return_value=mock):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            _, _, _, _, memory, *_ = analyze_ticket(*_VALID_INPUTS)
        assert "No prior tickets" in memory


class TestAnalyzeTicketSimilarPanel:
    def test_similar_shows_case(self):
        with patch("frontend.gradio_app._get_graph", return_value=_mock_graph()):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            _, _, _, _, _, similar, _ = analyze_ticket(*_VALID_INPUTS)
        assert "TKT-SIM-1" in similar

    def test_no_similar_shows_placeholder(self):
        mock = _mock_graph()
        mock.invoke.return_value = {**_MOCK_RESULT, "similar_cases": []}
        with patch("frontend.gradio_app._get_graph", return_value=mock):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            _, _, _, _, _, similar, _ = analyze_ticket(*_VALID_INPUTS)
        assert "No similar" in similar


class TestAnalyzeTicketTracePanel:
    def test_trace_returns_string(self):
        with patch("frontend.gradio_app._get_graph", return_value=_mock_graph()):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            *_, trace = analyze_ticket(*_VALID_INPUTS)
        assert isinstance(trace, str) and len(trace) > 0

    def test_no_trace_id_shows_placeholder(self):
        mock = _mock_graph()
        mock.invoke.return_value = {**_MOCK_RESULT, "langfuse_trace_id": ""}
        with patch("frontend.gradio_app._get_graph", return_value=mock):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            *_, trace = analyze_ticket(*_VALID_INPUTS)
        assert "not configured" in trace or "no trace" in trace.lower()


class TestAnalyzeTicketEscalation:
    def test_escalated_shows_yes_badge(self):
        mock = _mock_graph()
        mock.invoke.return_value = {
            **_MOCK_RESULT,
            "escalation_required": True,
            "escalation_reason": "High-value refund request",
        }
        with patch("frontend.gradio_app._get_graph", return_value=mock):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            decision, *_ = analyze_ticket(*_VALID_INPUTS)
        assert "YES" in decision  # badge text inside HTML span
        assert "High-value refund" in decision


class TestAutoGeneratedIds:
    def test_blank_ticket_id_gets_auto_id(self):
        with patch("frontend.gradio_app._get_graph", return_value=_mock_graph()):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            decision, *_ = analyze_ticket("", "", "Subject", "Message", "email", "low")
        assert "TKT-" in decision

    def test_blank_customer_id_gets_auto_id(self):
        with patch("frontend.gradio_app._get_graph", return_value=_mock_graph()):
            from frontend.gradio_app import analyze_ticket  # noqa: PLC0415
            decision, *_ = analyze_ticket("", "", "Subject", "Message", "email", "low")
        assert "CUST-DEMO-" in decision
