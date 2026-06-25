"""Unit tests for all 13 Phase-8 LangChain agent tools.

Each tool class covers:
  - happy-path output schema
  - error / fallback handling
  - key field assertions
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from agents.nodes.classify_ticket import ClassificationOutput
from config.constants import Department, TicketCategory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_response(content: str, prompt_tokens: int = 50, completion_tokens: int = 25) -> MagicMock:
    """Return a mock AIMessage-like object with content and token metadata."""
    resp = MagicMock()
    resp.content = content
    resp.response_metadata = {
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
    }
    resp.usage_metadata = None
    return resp


# ---------------------------------------------------------------------------
# classify_ticket
# ---------------------------------------------------------------------------

class TestClassifyTicketTool:
    def test_happy_path_returns_classification(self):
        from tools.classify_ticket_tool import classify_ticket

        mock_result = ClassificationOutput(
            classification=TicketCategory.BILLING.value,
            confidence_score=0.92,
            reasoning="Customer mentioned invoice amount.",
        )

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_structured = MagicMock()
            mock_cls.return_value.with_structured_output.return_value = mock_structured
            mock_structured.return_value = mock_result
            mock_structured.invoke.return_value = mock_result

            result = classify_ticket.invoke(
                {"subject": "Invoice issue", "message": "My invoice is wrong."}
            )

        assert result["classification"] == TicketCategory.BILLING.value
        assert result["confidence_score"] == 0.92
        assert isinstance(result["reasoning"], str)

    def test_output_has_required_keys(self):
        from tools.classify_ticket_tool import classify_ticket

        mock_result = ClassificationOutput(
            classification=TicketCategory.GENERAL_INQUIRY.value,
            confidence_score=0.6,
            reasoning="General inquiry.",
        )

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_structured = MagicMock()
            mock_cls.return_value.with_structured_output.return_value = mock_structured
            mock_structured.return_value = mock_result
            mock_structured.invoke.return_value = mock_result

            result = classify_ticket.invoke(
                {"subject": "Hello", "message": "Just asking", "customer_history": "None"}
            )

        assert {"classification", "confidence_score", "reasoning"} <= set(result.keys())

    def test_llm_error_triggers_keyword_fallback(self):
        from tools.classify_ticket_tool import classify_ticket

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.side_effect = Exception("API unavailable")

            result = classify_ticket.invoke(
                {"subject": "refund request", "message": "I want my money back"}
            )

        assert result["classification"] in [c.value for c in TicketCategory]
        assert result["confidence_score"] == 0.0
        assert "fallback" in result["reasoning"].lower()

    def test_confidence_score_rounded(self):
        from tools.classify_ticket_tool import classify_ticket

        mock_result = ClassificationOutput(
            classification=TicketCategory.BILLING.value,
            confidence_score=0.123456789,
            reasoning="Billing issue detected.",
        )

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_structured = MagicMock()
            mock_cls.return_value.with_structured_output.return_value = mock_structured
            mock_structured.return_value = mock_result
            mock_structured.invoke.return_value = mock_result

            result = classify_ticket.invoke(
                {"subject": "Billing", "message": "Charge issue"}
            )

        # Should be rounded to 4 decimal places
        assert result["confidence_score"] == round(0.123456789, 4)


# ---------------------------------------------------------------------------
# retrieve_policy
# ---------------------------------------------------------------------------

class TestRetrievePolicyTool:
    def test_returns_formatted_policy_text(self):
        from tools.retrieve_policy_tool import retrieve_policy

        mock_chunks = [
            {"document": "Refunds are processed within 5 business days."},
            {"document": "Billing inquiries can be sent to billing@nexus.com."},
        ]
        formatted = "Refunds are processed within 5 business days.\n\nBilling inquiries..."

        with patch("tools.retrieve_policy_tool.retrieve_policy_chunks", return_value=mock_chunks), \
             patch("tools.retrieve_policy_tool.format_context", return_value=formatted):
            result = retrieve_policy.invoke({"query": "refund policy"})

        assert result["policy_text"] == formatted
        assert result["chunks_retrieved"] == 2

    def test_empty_collection_returns_empty_string(self):
        from tools.retrieve_policy_tool import retrieve_policy

        with patch("tools.retrieve_policy_tool.retrieve_policy_chunks", return_value=[]), \
             patch("tools.retrieve_policy_tool.format_context", return_value=""):
            result = retrieve_policy.invoke({"query": "anything"})

        assert result["policy_text"] == ""
        assert result["chunks_retrieved"] == 0

    def test_exception_returns_empty(self):
        from tools.retrieve_policy_tool import retrieve_policy

        with patch("tools.retrieve_policy_tool.retrieve_policy_chunks", side_effect=RuntimeError("DB error")):
            result = retrieve_policy.invoke({"query": "billing"})

        assert result["policy_text"] == ""
        assert result["chunks_retrieved"] == 0

    def test_custom_n_results_passed_through(self):
        from tools.retrieve_policy_tool import retrieve_policy

        with patch("tools.retrieve_policy_tool.retrieve_policy_chunks", return_value=[]) as mock_fn, \
             patch("tools.retrieve_policy_tool.format_context", return_value=""):
            retrieve_policy.invoke({"query": "tech", "n_results": 3})

        mock_fn.assert_called_once_with("tech", 3)


# ---------------------------------------------------------------------------
# retrieve_memory
# ---------------------------------------------------------------------------

class TestRetrieveMemoryTool:
    def _make_history(self, ticket_count=2, escalations=1, refunds=0):
        history = MagicMock()
        history.total_tickets = ticket_count
        history.previous_escalations = escalations
        history.previous_refunds = refunds
        tickets = []
        for i in range(ticket_count):
            t = MagicMock()
            t.ticket_id = f"T{i}"
            t.subject = f"Subject {i}"
            t.classification = "Billing"
            t.resolution = "Resolved"
            t.created_at = datetime.now(timezone.utc)
            tickets.append(t)
        history.tickets = tickets
        return history

    def test_happy_path_returns_history(self):
        from tools.retrieve_memory_tool import retrieve_memory

        mock_history = self._make_history(ticket_count=2, escalations=1, refunds=0)
        mock_db = MagicMock()

        with patch("tools.retrieve_memory_tool.get_customer_history", return_value=mock_history), \
             patch("database.session.SessionLocal", return_value=mock_db):
            result = retrieve_memory.invoke({"customer_id": "C001"})

        assert result["total_tickets"] == 2
        assert result["prior_escalations"] == 1
        assert result["prior_refunds"] == 0
        assert len(result["customer_history"]) == 2
        mock_db.close.assert_called_once()

    def test_db_error_returns_empty(self):
        from tools.retrieve_memory_tool import retrieve_memory

        mock_db = MagicMock()

        with patch("tools.retrieve_memory_tool.get_customer_history", side_effect=Exception("DB error")), \
             patch("database.session.SessionLocal", return_value=mock_db):
            result = retrieve_memory.invoke({"customer_id": "C001"})

        assert result["total_tickets"] == 0
        assert result["prior_escalations"] == 0
        assert result["customer_history"] == []
        mock_db.close.assert_called_once()

    def test_output_has_required_keys(self):
        from tools.retrieve_memory_tool import retrieve_memory

        mock_history = self._make_history(ticket_count=0, escalations=0, refunds=0)
        mock_db = MagicMock()

        with patch("tools.retrieve_memory_tool.get_customer_history", return_value=mock_history), \
             patch("database.session.SessionLocal", return_value=mock_db):
            result = retrieve_memory.invoke({"customer_id": "C999"})

        assert {"customer_history", "total_tickets", "prior_escalations", "prior_refunds"} <= set(result.keys())


# ---------------------------------------------------------------------------
# retrieve_similar_cases
# ---------------------------------------------------------------------------

class TestRetrieveSimilarCasesTool:
    def test_happy_path_returns_cases(self):
        from tools.retrieve_similar_cases_tool import retrieve_similar_cases

        mock_results = [
            {"metadata": {"ticket_id": "T1", "subject": "Billing issue", "classification": "Billing", "resolution": "Refunded"}, "distance": 0.2},
            {"metadata": {"ticket_id": "T2", "subject": "Login fail", "classification": "Account Access", "resolution": "Reset"}, "distance": 0.4},
        ]

        with patch("tools.retrieve_similar_cases_tool.retrieve_similar", return_value=mock_results):
            result = retrieve_similar_cases.invoke({"query": "account login"})

        assert result["count"] == 2
        assert len(result["similar_cases"]) == 2
        assert result["similar_cases"][0]["ticket_id"] == "T1"
        assert 0 < result["similar_cases"][0]["similarity_score"] <= 1.0

    def test_empty_result_returns_empty_list(self):
        from tools.retrieve_similar_cases_tool import retrieve_similar_cases

        with patch("tools.retrieve_similar_cases_tool.retrieve_similar", return_value=[]):
            result = retrieve_similar_cases.invoke({"query": "anything"})

        assert result["count"] == 0
        assert result["similar_cases"] == []

    def test_exception_returns_empty(self):
        from tools.retrieve_similar_cases_tool import retrieve_similar_cases

        with patch("tools.retrieve_similar_cases_tool.retrieve_similar", side_effect=RuntimeError("ChromaDB error")):
            result = retrieve_similar_cases.invoke({"query": "test"})

        assert result["count"] == 0
        assert result["similar_cases"] == []

    def test_similarity_score_computed_from_distance(self):
        from tools.retrieve_similar_cases_tool import retrieve_similar_cases

        mock_results = [{"metadata": {}, "distance": 0.0}]

        with patch("tools.retrieve_similar_cases_tool.retrieve_similar", return_value=mock_results):
            result = retrieve_similar_cases.invoke({"query": "exact match"})

        assert result["similar_cases"][0]["similarity_score"] == 1.0


# ---------------------------------------------------------------------------
# route_ticket
# ---------------------------------------------------------------------------

class TestRouteTicketTool:
    @pytest.mark.parametrize("category, expected_dept", [
        (TicketCategory.BILLING.value, Department.BILLING_TEAM.value),
        (TicketCategory.TECHNICAL_SUPPORT.value, Department.TECHNICAL_SUPPORT_TEAM.value),
        (TicketCategory.PRODUCT_QUESTIONS.value, Department.PRODUCT_TEAM.value),
    ])
    def test_known_categories_route_correctly(self, category, expected_dept):
        from tools.route_ticket_tool import route_ticket

        result = route_ticket.invoke({"classification": category})

        assert result["department"] == expected_dept
        assert isinstance(result["routing_reason"], str)

    def test_unknown_category_defaults_to_customer_success(self):
        from tools.route_ticket_tool import route_ticket

        result = route_ticket.invoke({"classification": "Totally Unknown Category"})

        assert result["department"] == Department.CUSTOMER_SUCCESS_TEAM.value

    def test_output_has_required_keys(self):
        from tools.route_ticket_tool import route_ticket

        result = route_ticket.invoke({"classification": TicketCategory.GENERAL_INQUIRY.value})

        assert {"department", "routing_reason"} <= set(result.keys())


# ---------------------------------------------------------------------------
# draft_response
# ---------------------------------------------------------------------------

class TestDraftResponseTool:
    def test_happy_path_returns_draft(self):
        from tools.draft_response_tool import draft_response

        mock_resp = _make_llm_response("Thank you for contacting us.", 100, 40)

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_llm_instance = mock_cls.return_value
            mock_llm_instance.return_value = mock_resp
            mock_llm_instance.invoke.return_value = mock_resp

            result = draft_response.invoke({
                "subject": "Billing issue",
                "message": "My charge is wrong",
                "classification": "Billing",
                "policy_context": "Refunds in 5 days.",
            })

        assert isinstance(result["draft"], str)
        assert len(result["draft"]) > 0
        assert "tokens_used" in result
        assert "cost_usd" in result

    def test_llm_failure_returns_fallback_draft(self):
        from tools.draft_response_tool import draft_response, _FALLBACK_DRAFT

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.side_effect = Exception("OpenAI error")

            result = draft_response.invoke({
                "subject": "Issue",
                "message": "Help me",
                "classification": "General Inquiry",
            })

        assert result["draft"] == _FALLBACK_DRAFT
        assert result["tokens_used"] == 0
        assert result["cost_usd"] == 0.0

    def test_output_has_required_keys(self):
        from tools.draft_response_tool import draft_response

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.side_effect = Exception("skip LLM")

            result = draft_response.invoke({
                "subject": "Test",
                "message": "Test message",
                "classification": "General Inquiry",
            })

        assert {"draft", "tokens_used", "cost_usd"} <= set(result.keys())


# ---------------------------------------------------------------------------
# summarize_ticket
# ---------------------------------------------------------------------------

class TestSummarizeTicketTool:
    def test_happy_path_returns_summary(self):
        from tools.summarize_ticket_tool import summarize_ticket

        mock_resp = _make_llm_response("Billing ticket from C001 routed to Billing Team.", 60, 20)

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_llm_instance = mock_cls.return_value
            mock_llm_instance.return_value = mock_resp
            mock_llm_instance.invoke.return_value = mock_resp

            result = summarize_ticket.invoke({
                "subject": "Billing problem",
                "classification": "Billing",
                "customer_id": "C001",
                "routing_decision": "Billing Team",
            })

        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    def test_llm_failure_returns_fallback_summary(self):
        from tools.summarize_ticket_tool import summarize_ticket

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.side_effect = Exception("LLM down")

            result = summarize_ticket.invoke({
                "subject": "Password reset",
                "classification": "Account Access",
                "customer_id": "C002",
                "routing_decision": "Technical Support Team",
                "escalated": False,
            })

        assert "Account Access" in result["summary"]
        assert "C002" in result["summary"]

    def test_escalated_flag_reflected_in_fallback(self):
        from tools.summarize_ticket_tool import summarize_ticket

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.side_effect = Exception("LLM down")

            result = summarize_ticket.invoke({
                "subject": "Urgent billing issue",
                "classification": "Billing",
                "customer_id": "C003",
                "routing_decision": "Human Review Queue",
                "escalated": True,
            })

        assert "Escalated" in result["summary"]

    def test_output_has_summary_key(self):
        from tools.summarize_ticket_tool import summarize_ticket

        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.side_effect = Exception("skip")

            result = summarize_ticket.invoke({
                "subject": "Test",
                "classification": "General Inquiry",
                "customer_id": "C999",
                "routing_decision": "Customer Success Team",
            })

        assert "summary" in result


# ---------------------------------------------------------------------------
# escalate_to_human
# ---------------------------------------------------------------------------

class TestEscalateToHumanTool:
    def test_happy_path_returns_escalation(self):
        from tools.escalate_to_human_tool import escalate_to_human

        mock_escalation = MagicMock()
        mock_escalation.id = 42
        mock_db = MagicMock()

        with patch("tools.escalate_to_human_tool.save_escalation", return_value=mock_escalation), \
             patch("database.session.SessionLocal", return_value=mock_db):
            result = escalate_to_human.invoke({
                "ticket_id": "T001",
                "reason": "Low confidence score",
                "confidence_score": 0.3,
            })

        assert result["escalated"] is True
        assert result["escalation_id"] == 42
        assert result["assigned_queue"] == Department.HUMAN_REVIEW_QUEUE.value
        assert isinstance(result["escalated_at"], str)
        mock_db.close.assert_called_once()

    def test_db_error_returns_escalated_false(self):
        from tools.escalate_to_human_tool import escalate_to_human

        mock_db = MagicMock()

        with patch("tools.escalate_to_human_tool.save_escalation", side_effect=Exception("DB down")), \
             patch("database.session.SessionLocal", return_value=mock_db):
            result = escalate_to_human.invoke({
                "ticket_id": "T002",
                "reason": "Keyword match",
                "confidence_score": 0.5,
            })

        assert result["escalated"] is False
        assert result["escalation_id"] is None
        assert result["assigned_queue"] == Department.HUMAN_REVIEW_QUEUE.value
        mock_db.close.assert_called_once()

    def test_output_has_required_keys(self):
        from tools.escalate_to_human_tool import escalate_to_human

        mock_escalation = MagicMock()
        mock_escalation.id = 1
        mock_db = MagicMock()

        with patch("tools.escalate_to_human_tool.save_escalation", return_value=mock_escalation), \
             patch("database.session.SessionLocal", return_value=mock_db):
            result = escalate_to_human.invoke({
                "ticket_id": "T003",
                "reason": "Test",
                "confidence_score": 0.5,
            })

        assert {"escalated", "escalation_id", "assigned_queue", "escalated_at"} <= set(result.keys())


# ---------------------------------------------------------------------------
# log_decision
# ---------------------------------------------------------------------------

class TestLogDecisionTool:
    def test_happy_path_logs_and_returns_id(self):
        from tools.log_decision_tool import log_decision

        mock_log = MagicMock()
        mock_log.id = 99
        mock_db = MagicMock()

        with patch("tools.log_decision_tool.log_agent_decision", return_value=mock_log), \
             patch("database.session.SessionLocal", return_value=mock_db):
            result = log_decision.invoke({
                "ticket_id": "T001",
                "classification": "Billing",
                "confidence_score": 0.85,
                "routing_decision": "Billing Team",
                "escalation_required": False,
                "tokens_used": 150,
                "cost_usd": 0.00012,
                "langfuse_trace_id": "trace-abc",
            })

        assert result["log_id"] == 99
        assert result["logged"] is True
        assert isinstance(result["logged_at"], str)
        mock_db.close.assert_called_once()

    def test_db_error_returns_logged_false(self):
        from tools.log_decision_tool import log_decision

        mock_db = MagicMock()

        with patch("tools.log_decision_tool.log_agent_decision", side_effect=Exception("DB failure")), \
             patch("database.session.SessionLocal", return_value=mock_db):
            result = log_decision.invoke({"ticket_id": "T002"})

        assert result["logged"] is False
        assert result["log_id"] is None
        mock_db.close.assert_called_once()

    def test_default_optional_fields(self):
        from tools.log_decision_tool import log_decision

        mock_log = MagicMock()
        mock_log.id = 1
        mock_db = MagicMock()

        with patch("tools.log_decision_tool.log_agent_decision", return_value=mock_log) as mock_fn, \
             patch("database.session.SessionLocal", return_value=mock_db):
            log_decision.invoke({"ticket_id": "T003"})

        call_kwargs = mock_fn.call_args
        assert call_kwargs is not None


# ---------------------------------------------------------------------------
# send_email (mock)
# ---------------------------------------------------------------------------

class TestSendEmailTool:
    def test_returns_sent_true(self):
        from tools.send_email_tool import send_email

        result = send_email.invoke({
            "to_email": "customer@example.com",
            "subject": "Re: Your support ticket",
            "body": "We have resolved your issue.",
            "ticket_id": "T001",
        })

        assert result["sent"] is True
        assert isinstance(result["message_id"], str)
        assert result["message_id"].startswith("msg-")
        assert isinstance(result["sent_at"], str)

    def test_output_has_required_keys(self):
        from tools.send_email_tool import send_email

        result = send_email.invoke({
            "to_email": "a@b.com",
            "subject": "Test",
            "body": "Body",
            "ticket_id": "T001",
        })

        assert {"sent", "message_id", "sent_at"} <= set(result.keys())

    def test_unique_message_ids(self):
        from tools.send_email_tool import send_email

        args = {"to_email": "a@b.com", "subject": "S", "body": "B", "ticket_id": "T"}
        r1 = send_email.invoke(args)
        r2 = send_email.invoke(args)

        assert r1["message_id"] != r2["message_id"]


# ---------------------------------------------------------------------------
# create_jira_ticket (mock)
# ---------------------------------------------------------------------------

class TestCreateJiraTicketTool:
    def test_returns_created_true(self):
        from tools.create_jira_ticket_tool import create_jira_ticket

        result = create_jira_ticket.invoke({
            "title": "Billing escalation",
            "description": "Customer reports double charge.",
            "priority": "High",
            "ticket_id": "T001",
            "customer_id": "C001",
        })

        assert result["created"] is True
        assert result["jira_ticket_id"].startswith("SUP-")
        assert "atlassian.net/browse/SUP-" in result["url"]
        assert isinstance(result["created_at"], str)

    def test_output_has_required_keys(self):
        from tools.create_jira_ticket_tool import create_jira_ticket

        result = create_jira_ticket.invoke({
            "title": "T",
            "description": "D",
            "ticket_id": "T1",
            "customer_id": "C1",
        })

        assert {"jira_ticket_id", "url", "created", "created_at"} <= set(result.keys())


# ---------------------------------------------------------------------------
# slack_notification (mock)
# ---------------------------------------------------------------------------

class TestSlackNotificationTool:
    def test_returns_sent_true(self):
        from tools.slack_notification_tool import slack_notification

        result = slack_notification.invoke({
            "channel": "#escalations",
            "message": "Ticket T001 escalated.",
            "ticket_id": "T001",
            "escalation_reason": "Low confidence",
        })

        assert result["sent"] is True
        assert result["channel"] == "#escalations"
        assert isinstance(result["timestamp"], str)

    def test_output_has_required_keys(self):
        from tools.slack_notification_tool import slack_notification

        result = slack_notification.invoke({
            "channel": "#support",
            "message": "Alert",
            "ticket_id": "T002",
        })

        assert {"sent", "channel", "timestamp"} <= set(result.keys())


# ---------------------------------------------------------------------------
# zendesk_mock
# ---------------------------------------------------------------------------

class TestZendeskMockTool:
    def test_returns_created_true(self):
        from tools.zendesk_mock_tool import create_zendesk_ticket

        result = create_zendesk_ticket.invoke({
            "subject": "Account locked",
            "description": "Cannot log in.",
            "customer_id": "C001",
            "priority": "high",
            "ticket_id": "T001",
        })

        assert result["created"] is True
        assert result["zendesk_id"].isdigit()
        assert "zendesk.com/tickets/" in result["url"]
        assert isinstance(result["created_at"], str)

    def test_output_has_required_keys(self):
        from tools.zendesk_mock_tool import create_zendesk_ticket

        result = create_zendesk_ticket.invoke({
            "subject": "Test",
            "description": "Desc",
            "customer_id": "C1",
            "ticket_id": "T1",
        })

        assert {"zendesk_id", "url", "created", "created_at"} <= set(result.keys())
