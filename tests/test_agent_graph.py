"""Tests for Phase 7 — LangGraph Agent Workflow.

Tests cover:
  - agents/confidence.py  (unit)
  - agents/prompts.py     (smoke)
  - agents/nodes/*        (unit, mocked LLM + DB)
  - agents/graph.py       (integration, mocked LLM + DB)

LLM calls are mocked via unittest.mock.patch so tests pass without
OpenAI / Anthropic billing credits.

DB calls in retrieve_long_term_memory and store_memory are mocked with
a lightweight in-memory SQLite session so the nodes remain independently
testable without depending on seeded data.
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents.confidence import (
    check_escalation_keywords,
    meets_threshold,
    should_escalate,
)
from agents.graph import build_graph
from agents.nodes.check_confidence import check_confidence_node
from agents.nodes.classify_ticket import _keyword_classify, classify_ticket_node
from agents.nodes.draft_response import draft_response_node
from agents.nodes.escalate_ticket import escalate_ticket_node
from agents.nodes.receive_ticket import receive_ticket_node
from agents.nodes.retrieve_policy import retrieve_policy_node
from agents.nodes.retrieve_semantic_memory import retrieve_semantic_memory_node
from agents.nodes.route_ticket import route_ticket_node
from agents.nodes.summarize_ticket import summarize_ticket_node
from agents.prompts import CLASSIFICATION_PROMPT, DRAFT_RESPONSE_PROMPT, SUMMARIZE_PROMPT
from api.schemas.ticket_schema import TicketInput
from config.constants import Department, TicketCategory, TicketChannel, TicketPriority


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def billing_ticket() -> TicketInput:
    return TicketInput(
        ticket_id="T-001",
        customer_id="C-001",
        subject="Invoice discrepancy",
        message="I was charged $150 but my plan is only $99/month. Please investigate.",
        channel=TicketChannel.EMAIL,
        priority=TicketPriority.HIGH,
        created_at=datetime(2024, 1, 15, 10, 0, 0),
    )


@pytest.fixture
def refund_ticket() -> TicketInput:
    return TicketInput(
        ticket_id="T-002",
        customer_id="C-002",
        subject="Request for refund",
        message="I would like a refund for last month's payment as I cancelled on time.",
        channel=TicketChannel.CHAT,
        priority=TicketPriority.MEDIUM,
        created_at=datetime(2024, 1, 16, 9, 0, 0),
    )


@pytest.fixture
def escalation_ticket() -> TicketInput:
    return TicketInput(
        ticket_id="T-003",
        customer_id="C-003",
        subject="Unauthorized charge",
        message="There is an unauthorized charge on my account. I will contact my lawyer if this isn't resolved.",
        channel=TicketChannel.EMAIL,
        priority=TicketPriority.HIGH,
        created_at=datetime(2024, 1, 17, 11, 0, 0),
    )


@pytest.fixture
def base_state(billing_ticket) -> dict:
    """Minimal AgentState dict with defaults for all required fields."""
    return {
        "ticket": billing_ticket,
        "customer_history": [],
        "similar_cases": [],
        "classification": "",
        "confidence_score": 0.0,
        "retrieved_policies": [],
        "draft_response": "",
        "routing_decision": "",
        "escalation_required": False,
        "escalation_reason": "",
        "summary": "",
        "audit_log": {},
        "langfuse_trace_id": "",
        "messages": [],
    }


# ── TestConfidenceModule ──────────────────────────────────────────────────────


class TestConfidenceModule:
    def test_check_escalation_keyword_found(self):
        triggered, keyword = check_escalation_keywords("I will sue you in court")
        assert triggered is True
        assert keyword == "court"

    def test_check_escalation_keyword_not_found(self):
        triggered, keyword = check_escalation_keywords("I need help with my invoice")
        assert triggered is False
        assert keyword == ""

    def test_check_escalation_keyword_case_insensitive(self):
        triggered, keyword = check_escalation_keywords("This is FRAUD")
        assert triggered is True
        assert keyword == "fraud"

    def test_check_escalation_keyword_phrase(self):
        triggered, keyword = check_escalation_keywords("I see an unauthorized charge on my statement")
        assert triggered is True
        assert keyword == "unauthorized charge"

    def test_meets_threshold_above(self):
        assert meets_threshold(0.8) is True

    def test_meets_threshold_equal(self):
        # Default threshold is 0.75
        assert meets_threshold(0.75) is True

    def test_meets_threshold_below(self):
        assert meets_threshold(0.5) is False

    def test_should_escalate_low_confidence(self, base_state):
        base_state["confidence_score"] = 0.4
        assert should_escalate(base_state) is True

    def test_should_escalate_keyword_trigger(self, base_state):
        base_state["confidence_score"] = 0.95
        base_state["ticket"] = TicketInput(
            ticket_id="T-X",
            customer_id="C-X",
            subject="Data breach",
            message="I believe there has been a data breach of my account.",
        )
        assert should_escalate(base_state) is True

    def test_should_not_escalate_high_confidence_no_keywords(self, base_state):
        base_state["confidence_score"] = 0.9
        base_state["ticket"] = TicketInput(
            ticket_id="T-Y",
            customer_id="C-Y",
            subject="Billing question",
            message="How do I update my payment method?",
        )
        assert should_escalate(base_state) is False


# ── TestReceiveTicketNode ─────────────────────────────────────────────────────


class TestReceiveTicketNode:
    def test_initialises_all_state_fields(self, billing_ticket):
        result = receive_ticket_node({"ticket": billing_ticket, "messages": []})
        assert result["classification"] == ""
        assert result["confidence_score"] == 0.0
        assert result["escalation_required"] is False
        assert result["retrieved_policies"] == []
        assert result["customer_history"] == []
        assert result["similar_cases"] == []

    def test_adds_human_message(self, billing_ticket):
        result = receive_ticket_node({"ticket": billing_ticket, "messages": []})
        messages = result["messages"]
        assert len(messages) == 1
        assert isinstance(messages[0], HumanMessage)
        assert billing_ticket.subject in messages[0].content
        assert billing_ticket.message in messages[0].content

    def test_audit_log_has_ticket_id(self, billing_ticket):
        result = receive_ticket_node({"ticket": billing_ticket, "messages": []})
        assert result["audit_log"]["ticket_id"] == "T-001"
        assert result["audit_log"]["customer_id"] == "C-001"

    def test_audit_log_has_received_at(self, billing_ticket):
        result = receive_ticket_node({"ticket": billing_ticket, "messages": []})
        assert "received_at" in result["audit_log"]


# ── TestRetrieveSemanticMemoryNode ────────────────────────────────────────────


class TestRetrieveSemanticMemoryNode:
    @patch("agents.nodes.retrieve_semantic_memory.retrieve_similar")
    def test_populates_similar_cases(self, mock_retrieve, base_state):
        mock_retrieve.return_value = [
            {
                "document": "Customer asked about billing overage.",
                "metadata": {
                    "ticket_id": "HT-001",
                    "subject": "Billing issue",
                    "classification": "Billing",
                    "resolution": "Refunded the overcharge.",
                },
                "distance": 0.2,
            }
        ]
        result = retrieve_semantic_memory_node(base_state)
        assert len(result["similar_cases"]) == 1
        case = result["similar_cases"][0]
        assert case["ticket_id"] == "HT-001"
        assert case["classification"] == "Billing"
        assert case["similarity_score"] > 0

    @patch("agents.nodes.retrieve_semantic_memory.retrieve_similar")
    def test_handles_empty_results(self, mock_retrieve, base_state):
        mock_retrieve.return_value = []
        result = retrieve_semantic_memory_node(base_state)
        assert result["similar_cases"] == []

    @patch("agents.nodes.retrieve_semantic_memory.retrieve_similar")
    def test_handles_retrieval_error(self, mock_retrieve, base_state):
        mock_retrieve.side_effect = Exception("ChromaDB unavailable")
        result = retrieve_semantic_memory_node(base_state)
        assert result["similar_cases"] == []


# ── TestKeywordClassifier ─────────────────────────────────────────────────────


class TestKeywordClassifier:
    def test_billing_keyword(self):
        assert _keyword_classify("Invoice problem", "I have a billing issue") == TicketCategory.BILLING.value

    def test_refund_keyword(self):
        assert _keyword_classify("Need refund", "I want my money back") == TicketCategory.REFUND.value

    def test_access_keyword(self):
        assert _keyword_classify("Can't login", "I am locked out of my account") == TicketCategory.ACCOUNT_ACCESS.value

    def test_technical_keyword(self):
        assert _keyword_classify("App crash", "The app keeps crashing with an error") == TicketCategory.TECHNICAL_SUPPORT.value

    def test_product_keyword(self):
        assert _keyword_classify("Feature question", "How to use this feature?") == TicketCategory.PRODUCT_QUESTIONS.value

    def test_default_general_inquiry(self):
        assert _keyword_classify("Hello", "Just saying hi") == TicketCategory.GENERAL_INQUIRY.value


# ── TestClassifyTicketNode ────────────────────────────────────────────────────


class TestClassifyTicketNode:
    def _make_llm_mock(self, classification: str, confidence: float, reasoning: str = "Test."):
        """Return a MagicMock that mimics ChatOpenAI.with_structured_output chain."""
        from agents.nodes.classify_ticket import ClassificationOutput

        output = ClassificationOutput(
            classification=classification,
            confidence_score=confidence,
            reasoning=reasoning,
        )

        # LangChain pipe: PROMPT | mock_structured
        # coerce_to_runnable wraps plain MagicMock in RunnableLambda, calling mock(input).
        # Set both return_value (for __call__) and invoke.return_value (for .invoke()).
        mock_structured = MagicMock()
        mock_structured.return_value = output
        mock_structured.invoke.return_value = output

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured

        return mock_llm

    @patch("agents.nodes.classify_ticket.ChatOpenAI")
    def test_classifies_billing_ticket(self, MockLLM, base_state):
        MockLLM.return_value = self._make_llm_mock("Billing", 0.92)
        result = classify_ticket_node(base_state)
        assert result["classification"] == "Billing"
        assert result["confidence_score"] == 0.92

    @patch("agents.nodes.classify_ticket.ChatOpenAI")
    def test_adds_ai_message(self, MockLLM, base_state):
        MockLLM.return_value = self._make_llm_mock("Billing", 0.88)
        result = classify_ticket_node(base_state)
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

    @patch("agents.nodes.classify_ticket.ChatOpenAI")
    def test_keyword_fallback_on_llm_error(self, MockLLM, base_state):
        MockLLM.side_effect = Exception("No credits")
        result = classify_ticket_node(base_state)
        # Billing ticket should fall back to Billing via keyword classifier
        assert result["classification"] == TicketCategory.BILLING.value
        assert result["confidence_score"] == 0.0

    @patch("agents.nodes.classify_ticket.ChatOpenAI")
    def test_audit_log_populated(self, MockLLM, base_state):
        MockLLM.return_value = self._make_llm_mock("Billing", 0.9, "Billing charge mentioned.")
        base_state["audit_log"] = {"ticket_id": "T-001"}
        result = classify_ticket_node(base_state)
        assert result["audit_log"]["classification"] == "Billing"
        assert result["audit_log"]["ticket_id"] == "T-001"  # preserved


# ── TestRetrievePolicyNode ────────────────────────────────────────────────────


class TestRetrievePolicyNode:
    @patch("agents.nodes.retrieve_policy.retrieve_policy_chunks")
    @patch("agents.nodes.retrieve_policy.format_context")
    def test_populates_retrieved_policies(self, mock_format, mock_retrieve, base_state):
        base_state["classification"] = "Billing"
        mock_retrieve.return_value = [{"document": "Policy text", "metadata": {}}]
        mock_format.return_value = "[Source: billing.md]\nPolicy text"
        result = retrieve_policy_node(base_state)
        assert len(result["retrieved_policies"]) == 1
        assert "Policy text" in result["retrieved_policies"][0]

    @patch("agents.nodes.retrieve_policy.retrieve_policy_chunks")
    @patch("agents.nodes.retrieve_policy.format_context")
    def test_handles_empty_chunks(self, mock_format, mock_retrieve, base_state):
        mock_retrieve.return_value = []
        mock_format.return_value = ""
        result = retrieve_policy_node(base_state)
        assert result["retrieved_policies"] == []

    @patch("agents.nodes.retrieve_policy.retrieve_policy_chunks")
    def test_handles_retrieval_error(self, mock_retrieve, base_state):
        mock_retrieve.side_effect = Exception("ChromaDB error")
        result = retrieve_policy_node(base_state)
        assert result["retrieved_policies"] == []


# ── TestDraftResponseNode ─────────────────────────────────────────────────────


class TestDraftResponseNode:
    @patch("agents.nodes.draft_response.ChatOpenAI")
    def test_sets_draft_response(self, MockLLM, base_state):
        mock_response = MagicMock()
        mock_response.content = "Thank you for contacting us. We will resolve your billing issue."

        mock_llm_instance = MagicMock()
        # LangChain coerce_to_runnable wraps MagicMock in RunnableLambda (calls mock(input)).
        # Set both return_value and invoke to be safe.
        mock_llm_instance.return_value = mock_response
        mock_llm_instance.invoke.return_value = mock_response
        MockLLM.return_value = mock_llm_instance

        base_state["classification"] = "Billing"
        base_state["retrieved_policies"] = ["Policy text here"]
        result = draft_response_node(base_state)
        assert "billing issue" in result["draft_response"]

    @patch("agents.nodes.draft_response.ChatOpenAI")
    def test_fallback_on_llm_error(self, MockLLM, base_state):
        MockLLM.side_effect = Exception("No credits")
        result = draft_response_node(base_state)
        assert len(result["draft_response"]) > 0
        # Fallback message should be non-empty
        assert "Nexus Software" in result["draft_response"] or "team" in result["draft_response"].lower()

    @patch("agents.nodes.draft_response.ChatOpenAI")
    def test_adds_ai_message(self, MockLLM, base_state):
        mock_response = MagicMock()
        mock_response.content = "We are looking into your billing query."

        mock_llm_instance = MagicMock()
        mock_llm_instance.return_value = mock_response
        mock_llm_instance.invoke.return_value = mock_response
        MockLLM.return_value = mock_llm_instance

        result = draft_response_node(base_state)
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)


# ── TestCheckConfidenceNode ───────────────────────────────────────────────────


class TestCheckConfidenceNode:
    def test_routes_high_confidence(self, base_state):
        base_state["confidence_score"] = 0.9
        assert check_confidence_node(base_state) == "route"

    def test_escalates_low_confidence(self, base_state):
        base_state["confidence_score"] = 0.3
        assert check_confidence_node(base_state) == "escalate"

    def test_escalates_on_keyword_regardless_of_confidence(self, escalation_ticket):
        state = {
            "ticket": escalation_ticket,
            "confidence_score": 0.95,
            "audit_log": {},
            "messages": [],
        }
        assert check_confidence_node(state) == "escalate"

    def test_routes_exactly_at_threshold(self, base_state):
        base_state["confidence_score"] = 0.75  # default threshold
        assert check_confidence_node(base_state) == "route"


# ── TestRouteTicketNode ───────────────────────────────────────────────────────


class TestRouteTicketNode:
    def test_routes_billing_to_billing_team(self, base_state):
        base_state["classification"] = TicketCategory.BILLING.value
        result = route_ticket_node(base_state)
        assert result["routing_decision"] == Department.BILLING_TEAM.value
        assert result["escalation_required"] is False

    def test_routes_technical_to_tech_team(self, base_state):
        base_state["classification"] = TicketCategory.TECHNICAL_SUPPORT.value
        result = route_ticket_node(base_state)
        assert result["routing_decision"] == Department.TECHNICAL_SUPPORT_TEAM.value

    def test_routes_refund_to_billing_team(self, base_state):
        base_state["classification"] = TicketCategory.REFUND.value
        result = route_ticket_node(base_state)
        assert result["routing_decision"] == Department.BILLING_TEAM.value

    def test_routes_product_questions_to_product_team(self, base_state):
        base_state["classification"] = TicketCategory.PRODUCT_QUESTIONS.value
        result = route_ticket_node(base_state)
        assert result["routing_decision"] == Department.PRODUCT_TEAM.value

    def test_unknown_classification_defaults_to_customer_success(self, base_state):
        base_state["classification"] = "Unknown Category"
        result = route_ticket_node(base_state)
        assert result["routing_decision"] == Department.CUSTOMER_SUCCESS_TEAM.value


# ── TestEscalateTicketNode ────────────────────────────────────────────────────


class TestEscalateTicketNode:
    def test_sets_escalation_required(self, base_state):
        base_state["confidence_score"] = 0.4
        result = escalate_ticket_node(base_state)
        assert result["escalation_required"] is True

    def test_routes_to_human_review_queue(self, base_state):
        result = escalate_ticket_node(base_state)
        assert result["routing_decision"] == Department.HUMAN_REVIEW_QUEUE.value

    def test_reason_mentions_low_confidence(self, base_state):
        base_state["confidence_score"] = 0.3
        result = escalate_ticket_node(base_state)
        assert "confidence" in result["escalation_reason"].lower()

    def test_reason_mentions_keyword(self, escalation_ticket):
        state = {
            "ticket": escalation_ticket,
            "confidence_score": 0.95,
            "audit_log": {},
            "messages": [],
        }
        result = escalate_ticket_node(state)
        assert "keyword" in result["escalation_reason"].lower() or "lawyer" in result["escalation_reason"].lower()

    def test_audit_log_has_escalation_fields(self, base_state):
        result = escalate_ticket_node(base_state)
        assert result["audit_log"]["escalation_required"] is True
        assert "escalation_reason" in result["audit_log"]


# ── TestSummarizeTicketNode ───────────────────────────────────────────────────


class TestSummarizeTicketNode:
    @patch("agents.nodes.summarize_ticket.ChatOpenAI")
    def test_sets_summary(self, MockLLM, base_state):
        mock_response = MagicMock()
        mock_response.content = "Billing ticket from customer C-001 re: invoice discrepancy. Routed to Billing Team."

        mock_llm_instance = MagicMock()
        mock_llm_instance.return_value = mock_response
        mock_llm_instance.invoke.return_value = mock_response
        MockLLM.return_value = mock_llm_instance

        base_state["classification"] = "Billing"
        base_state["routing_decision"] = "Billing Team"
        base_state["draft_response"] = "We will resolve your billing issue."
        result = summarize_ticket_node(base_state)
        assert "Billing" in result["summary"]

    @patch("agents.nodes.summarize_ticket.ChatOpenAI")
    def test_fallback_summary_on_llm_error(self, MockLLM, base_state):
        MockLLM.side_effect = Exception("No credits")
        base_state["classification"] = "Billing"
        base_state["routing_decision"] = "Billing Team"
        result = summarize_ticket_node(base_state)
        assert len(result["summary"]) > 0
        assert "Billing" in result["summary"]


# ── TestPromptsModule ─────────────────────────────────────────────────────────


class TestPromptsModule:
    def test_classification_prompt_has_expected_variables(self):
        variables = CLASSIFICATION_PROMPT.input_variables
        assert "subject" in variables
        assert "message" in variables
        assert "customer_history" in variables

    def test_draft_response_prompt_has_expected_variables(self):
        variables = DRAFT_RESPONSE_PROMPT.input_variables
        assert "subject" in variables
        assert "message" in variables
        assert "policy_context" in variables
        assert "similar_cases" in variables

    def test_summarize_prompt_has_expected_variables(self):
        variables = SUMMARIZE_PROMPT.input_variables
        assert "classification" in variables
        assert "routing_decision" in variables
        assert "customer_id" in variables


# ── TestGraphCompilation ──────────────────────────────────────────────────────


class TestGraphCompilation:
    def test_graph_compiles(self):
        g = build_graph()
        assert g is not None

    def test_graph_has_all_nodes(self):
        g = build_graph()
        node_names = set(g.nodes.keys())
        expected = {
            "__start__",
            "receive_ticket",
            "retrieve_long_term_memory",
            "retrieve_semantic_memory",
            "classify_ticket",
            "retrieve_policy",
            "draft_response",
            "route_ticket",
            "escalate_ticket",
            "summarize_ticket",
            "store_memory",
            "log_decision",
        }
        assert expected == node_names


# ── TestFullGraphIntegration ──────────────────────────────────────────────────


class TestFullGraphIntegration:
    """End-to-end graph tests with all external I/O mocked."""

    def _mock_llm_chain(self, content: str):
        """Helper: return mock LLM instances for classify, draft, and summarize."""
        from agents.nodes.classify_ticket import ClassificationOutput

        class_output = ClassificationOutput(
            classification="Billing",
            confidence_score=0.92,
            reasoning="Invoice charge detected.",
        )

        # classify_ticket: mock_structured is wrapped in RunnableLambda — call via mock(input)
        mock_structured = MagicMock()
        mock_structured.return_value = class_output
        mock_structured.invoke.return_value = class_output

        mock_classify_llm = MagicMock()
        mock_classify_llm.with_structured_output.return_value = mock_structured

        # draft_response / summarize_ticket
        mock_text_response = MagicMock()
        mock_text_response.content = content

        mock_text_llm = MagicMock()
        mock_text_llm.return_value = mock_text_response
        mock_text_llm.invoke.return_value = mock_text_response

        return mock_classify_llm, mock_text_llm

    @patch("observability.langfuse_client.create_trace", return_value="test-trace-id")
    @patch("observability.langfuse_client.add_retrieval_span")
    @patch("observability.langfuse_client.update_trace")
    @patch("observability.langfuse_client.get_callback_handler", return_value=None)
    @patch("agents.nodes.store_memory.SessionLocal")
    @patch("agents.nodes.retrieve_long_term_memory.SessionLocal")
    @patch("agents.nodes.retrieve_semantic_memory.retrieve_similar")
    @patch("agents.nodes.retrieve_policy.retrieve_policy_chunks")
    @patch("agents.nodes.retrieve_policy.format_context")
    @patch("agents.nodes.summarize_ticket.ChatOpenAI")
    @patch("agents.nodes.draft_response.ChatOpenAI")
    @patch("agents.nodes.classify_ticket.ChatOpenAI")
    def test_full_graph_routing_path(
        self,
        MockClassifyLLM,
        MockDraftLLM,
        MockSummarizeLLM,
        mock_format_ctx,
        mock_retrieve_policy,
        mock_retrieve_similar,
        MockMemorySL,
        MockStoreSL,
        mock_get_handler,
        mock_update_trace,
        mock_add_span,
        mock_create_trace,
        billing_ticket,
    ):
        """Full graph: high-confidence billing ticket should route (not escalate)."""
        # LLM mocks — classify gets structured mock, draft/summarize get plain text mock
        mock_classify_llm, mock_text_llm = self._mock_llm_chain("We will resolve your billing issue.")
        MockClassifyLLM.return_value = mock_classify_llm
        MockDraftLLM.return_value = mock_text_llm
        MockSummarizeLLM.return_value = mock_text_llm

        # RAG mocks
        mock_retrieve_policy.return_value = [{"document": "Billing policy text.", "metadata": {}}]
        mock_format_ctx.return_value = "[Source: billing.md]\nBilling policy text."

        # Semantic memory mock
        mock_retrieve_similar.return_value = []

        # DB session mocks (long-term memory + store)
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)

        mock_history = MagicMock()
        mock_history.tickets = []
        mock_history.total_tickets = 0
        mock_history.previous_escalations = 0
        mock_history.previous_refunds = 0

        from memory.customer_history import get_customer_history
        with patch("agents.nodes.retrieve_long_term_memory.get_customer_history", return_value=mock_history):
            MockMemorySL.return_value = mock_db
            MockStoreSL.return_value = mock_db

            g = build_graph()
            result = g.invoke({"ticket": billing_ticket, "messages": []})

        assert result["classification"] == "Billing"
        assert result["confidence_score"] == 0.92
        assert result["escalation_required"] is False
        assert result["routing_decision"] == Department.BILLING_TEAM.value
        assert len(result["draft_response"]) > 0
        assert len(result["summary"]) > 0

    @patch("observability.langfuse_client.create_trace", return_value="test-trace-id")
    @patch("observability.langfuse_client.add_retrieval_span")
    @patch("observability.langfuse_client.update_trace")
    @patch("observability.langfuse_client.get_callback_handler", return_value=None)
    @patch("agents.nodes.store_memory.SessionLocal")
    @patch("agents.nodes.retrieve_long_term_memory.SessionLocal")
    @patch("agents.nodes.retrieve_semantic_memory.retrieve_similar")
    @patch("agents.nodes.retrieve_policy.retrieve_policy_chunks")
    @patch("agents.nodes.retrieve_policy.format_context")
    @patch("agents.nodes.summarize_ticket.ChatOpenAI")
    @patch("agents.nodes.draft_response.ChatOpenAI")
    @patch("agents.nodes.classify_ticket.ChatOpenAI")
    def test_full_graph_escalation_path(
        self,
        MockClassifyLLM,
        MockDraftLLM,
        MockSummarizeLLM,
        mock_format_ctx,
        mock_retrieve_policy,
        mock_retrieve_similar,
        MockMemorySL,
        MockStoreSL,
        mock_get_handler,
        mock_update_trace,
        mock_add_span,
        mock_create_trace,
        escalation_ticket,
    ):
        """Full graph: keyword-trigger ticket should escalate."""
        from agents.nodes.classify_ticket import ClassificationOutput

        class_output = ClassificationOutput(
            classification="Billing",
            confidence_score=0.88,  # high confidence but keyword forces escalation
            reasoning="Billing overage.",
        )

        mock_structured = MagicMock()
        mock_structured.return_value = class_output
        mock_structured.invoke.return_value = class_output
        mock_classify_llm = MagicMock()
        mock_classify_llm.with_structured_output.return_value = mock_structured

        mock_text_response = MagicMock()
        mock_text_response.content = "We will escalate this to our team."
        mock_text_llm = MagicMock()
        mock_text_llm.return_value = mock_text_response
        mock_text_llm.invoke.return_value = mock_text_response

        MockClassifyLLM.return_value = mock_classify_llm
        MockDraftLLM.return_value = mock_text_llm
        MockSummarizeLLM.return_value = mock_text_llm

        mock_retrieve_policy.return_value = []
        mock_format_ctx.return_value = ""
        mock_retrieve_similar.return_value = []

        mock_db = MagicMock()
        mock_history = MagicMock()
        mock_history.tickets = []
        mock_history.total_tickets = 0
        mock_history.previous_escalations = 0
        mock_history.previous_refunds = 0

        with patch("agents.nodes.retrieve_long_term_memory.get_customer_history", return_value=mock_history):
            MockMemorySL.return_value = mock_db
            MockStoreSL.return_value = mock_db

            g = build_graph()
            result = g.invoke({"ticket": escalation_ticket, "messages": []})

        assert result["escalation_required"] is True
        assert result["routing_decision"] == Department.HUMAN_REVIEW_QUEUE.value
        assert len(result["escalation_reason"]) > 0

    @patch("observability.langfuse_client.create_trace", return_value="test-trace-id")
    @patch("observability.langfuse_client.add_retrieval_span")
    @patch("observability.langfuse_client.update_trace")
    @patch("observability.langfuse_client.get_callback_handler", return_value=None)
    @patch("agents.nodes.store_memory.SessionLocal")
    @patch("agents.nodes.retrieve_long_term_memory.SessionLocal")
    @patch("agents.nodes.retrieve_semantic_memory.retrieve_similar")
    @patch("agents.nodes.retrieve_policy.retrieve_policy_chunks")
    @patch("agents.nodes.retrieve_policy.format_context")
    @patch("agents.nodes.summarize_ticket.ChatOpenAI")
    @patch("agents.nodes.draft_response.ChatOpenAI")
    @patch("agents.nodes.classify_ticket.ChatOpenAI")
    def test_full_graph_llm_unavailable_fallback(
        self,
        MockClassifyLLM,
        MockDraftLLM,
        MockSummarizeLLM,
        mock_format_ctx,
        mock_retrieve_policy,
        mock_retrieve_similar,
        MockMemorySL,
        MockStoreSL,
        mock_get_handler,
        mock_update_trace,
        mock_add_span,
        mock_create_trace,
        billing_ticket,
    ):
        """Full graph: when all LLMs fail, the graph must not crash.

        The keyword fallback classifier returns 'Billing' with confidence=0.0,
        which should trigger escalation via the confidence gate.
        """
        MockClassifyLLM.side_effect = Exception("No credits")
        MockDraftLLM.side_effect = Exception("No credits")
        MockSummarizeLLM.side_effect = Exception("No credits")

        mock_retrieve_policy.return_value = []
        mock_format_ctx.return_value = ""
        mock_retrieve_similar.return_value = []

        mock_db = MagicMock()
        mock_history = MagicMock()
        mock_history.tickets = []
        mock_history.total_tickets = 0
        mock_history.previous_escalations = 0
        mock_history.previous_refunds = 0

        with patch("agents.nodes.retrieve_long_term_memory.get_customer_history", return_value=mock_history):
            MockMemorySL.return_value = mock_db
            MockStoreSL.return_value = mock_db

            g = build_graph()
            result = g.invoke({"ticket": billing_ticket, "messages": []})

        # Keyword classifier gives confidence=0.0 → should escalate
        assert result["escalation_required"] is True
        assert len(result["draft_response"]) > 0   # fallback response used
        assert len(result["summary"]) > 0           # fallback summary used
