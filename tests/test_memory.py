"""Tests for the Phase 6 Memory Layer.

Covers all 8 modules: short_term_memory, long_term_memory, semantic_memory,
conversation_history, customer_history, ticket_memory, memory_retriever,
memory_manager.

Uses an in-memory SQLite database and an ephemeral ChromaDB client so
no external services or files are needed. All tests run without OpenAI
billing credits — mock embeddings activate automatically.
"""

from datetime import datetime

import chromadb
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.schemas.ticket_schema import TicketInput
from config.constants import TicketChannel, TicketPriority
from database.db import Base
from database.models import Customer, Escalation, Ticket


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """In-memory SQLite session — created fresh for every test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def ephemeral_chroma(monkeypatch):
    """Replace _get_client with an in-memory ChromaDB client."""
    client = chromadb.EphemeralClient()
    monkeypatch.setattr("rag.vector_store._get_client", lambda: client)
    return client


@pytest.fixture
def sample_ticket():
    return TicketInput(
        ticket_id="TKT-TEST-001",
        customer_id="CUST-TEST-001",
        subject="Refund for annual subscription",
        message="I would like a refund for my annual subscription.",
        channel=TicketChannel.EMAIL,
        priority=TicketPriority.MEDIUM,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def saved_ticket(db_session, sample_ticket):
    """Insert a ticket and its customer into the in-memory DB."""
    from memory.long_term_memory import save_ticket
    return save_ticket(db_session, sample_ticket)


# ---------------------------------------------------------------------------
# short_term_memory
# ---------------------------------------------------------------------------


class TestShortTermMemory:
    def test_set_classification_returns_correct_dict(self):
        from memory.short_term_memory import set_classification
        result = set_classification("Billing", 0.85)
        assert result == {"classification": "Billing", "confidence_score": 0.85}

    def test_set_escalation_sets_required_true(self):
        from memory.short_term_memory import set_escalation
        result = set_escalation("GDPR request")
        assert result["escalation_required"] is True
        assert result["escalation_reason"] == "GDPR request"

    def test_set_draft_response(self):
        from memory.short_term_memory import set_draft_response
        result = set_draft_response("Here is your refund.")
        assert result == {"draft_response": "Here is your refund."}

    def test_set_routing_decision(self):
        from memory.short_term_memory import set_routing_decision
        result = set_routing_decision("Billing Team")
        assert result == {"routing_decision": "Billing Team"}

    def test_set_memory_context(self):
        from memory.short_term_memory import set_memory_context
        result = set_memory_context([{"ticket_id": "T1"}], [{"ticket_id": "T2"}])
        assert result["customer_history"] == [{"ticket_id": "T1"}]
        assert result["similar_cases"] == [{"ticket_id": "T2"}]

    def test_get_classification_defaults_empty(self):
        from memory.short_term_memory import get_classification
        assert get_classification({}) == ""

    def test_get_confidence_defaults_zero(self):
        from memory.short_term_memory import get_confidence
        assert get_confidence({}) == 0.0

    def test_is_escalated_defaults_false(self):
        from memory.short_term_memory import is_escalated
        assert is_escalated({}) is False


# ---------------------------------------------------------------------------
# long_term_memory
# ---------------------------------------------------------------------------


class TestLongTermMemory:
    def test_get_or_create_customer_creates_new(self, db_session):
        from memory.long_term_memory import get_or_create_customer
        customer = get_or_create_customer(db_session, "CUST-NEW")
        assert customer.customer_id == "CUST-NEW"

    def test_get_or_create_customer_is_idempotent(self, db_session):
        from memory.long_term_memory import get_or_create_customer
        c1 = get_or_create_customer(db_session, "CUST-IDEM")
        c2 = get_or_create_customer(db_session, "CUST-IDEM")
        assert c1.id == c2.id

    def test_save_ticket_creates_row(self, db_session, sample_ticket):
        from memory.long_term_memory import save_ticket
        ticket = save_ticket(db_session, sample_ticket)
        assert ticket.ticket_id == sample_ticket.ticket_id

    def test_save_ticket_is_idempotent(self, db_session, sample_ticket):
        from memory.long_term_memory import save_ticket
        t1 = save_ticket(db_session, sample_ticket)
        t2 = save_ticket(db_session, sample_ticket)
        assert t1.id == t2.id

    def test_save_ticket_creates_customer_automatically(self, db_session, sample_ticket):
        from memory.long_term_memory import save_ticket, get_customer_by_id
        save_ticket(db_session, sample_ticket)
        customer = get_customer_by_id(db_session, sample_ticket.customer_id)
        assert customer is not None

    def test_get_customer_tickets_returns_list(self, db_session, saved_ticket):
        from memory.long_term_memory import get_customer_tickets
        tickets = get_customer_tickets(db_session, saved_ticket.customer_id)
        assert len(tickets) >= 1

    def test_get_customer_tickets_empty_for_unknown_customer(self, db_session):
        from memory.long_term_memory import get_customer_tickets
        assert get_customer_tickets(db_session, "UNKNOWN") == []

    def test_update_ticket_classification(self, db_session, saved_ticket):
        from memory.long_term_memory import update_ticket_classification, get_ticket_by_id
        update_ticket_classification(db_session, saved_ticket.ticket_id, "Billing", 0.91)
        updated = get_ticket_by_id(db_session, saved_ticket.ticket_id)
        assert updated.classification == "Billing"
        assert abs(updated.confidence_score - 0.91) < 1e-6

    def test_update_ticket_classification_unknown_returns_none(self, db_session):
        from memory.long_term_memory import update_ticket_classification
        result = update_ticket_classification(db_session, "NONEXISTENT", "Billing", 0.5)
        assert result is None


# ---------------------------------------------------------------------------
# semantic_memory
# ---------------------------------------------------------------------------


class TestSemanticMemory:
    def test_index_ticket_adds_to_collection(self, ephemeral_chroma):
        from memory.semantic_memory import index_ticket, retrieve_similar
        index_ticket("TKT-SEM-001", "Refund request after 30 days.", {"classification": "Refund"})
        results = retrieve_similar("refund policy")
        assert len(results) >= 1

    def test_retrieve_similar_empty_returns_empty(self, ephemeral_chroma):
        from memory.semantic_memory import retrieve_similar
        from rag.vector_store import delete_collection, TICKETS_COLLECTION
        delete_collection(TICKETS_COLLECTION)  # clear any state from prior tests
        results = retrieve_similar("any query")
        assert results == []

    def test_index_tickets_batch(self, ephemeral_chroma):
        from memory.semantic_memory import index_tickets_batch, retrieve_similar
        tickets = [
            {"ticket_id": "TKT-B1", "text": "Billing dispute on invoice."},
            {"ticket_id": "TKT-B2", "text": "Cannot access account after password reset."},
        ]
        count = index_tickets_batch(tickets)
        assert count == 2

    def test_index_tickets_batch_empty(self, ephemeral_chroma):
        from memory.semantic_memory import index_tickets_batch
        assert index_tickets_batch([]) == 0

    def test_retrieve_similar_respects_n_results(self, ephemeral_chroma):
        from memory.semantic_memory import index_ticket, retrieve_similar
        for i in range(5):
            index_ticket(f"TKT-N{i}", f"Ticket text number {i}.", {})
        results = retrieve_similar("ticket text", n_results=2)
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# conversation_history
# ---------------------------------------------------------------------------


class TestConversationHistory:
    def test_build_human_message(self):
        from memory.conversation_history import build_human_message
        msg = build_human_message("I need help.")
        assert isinstance(msg, HumanMessage)
        assert msg.content == "I need help."

    def test_build_ai_message(self):
        from memory.conversation_history import build_ai_message
        msg = build_ai_message("How can I assist?")
        assert isinstance(msg, AIMessage)
        assert msg.content == "How can I assist?"

    def test_format_history_labels_correctly(self):
        from memory.conversation_history import build_human_message, build_ai_message, format_history
        msgs = [build_human_message("Hello"), build_ai_message("Hi there!")]
        text = format_history(msgs)
        assert "Customer: Hello" in text
        assert "Agent: Hi there!" in text

    def test_format_history_empty_returns_empty_string(self):
        from memory.conversation_history import format_history
        assert format_history([]) == ""

    def test_get_last_agent_message(self):
        from memory.conversation_history import build_human_message, build_ai_message, get_last_agent_message
        msgs = [build_human_message("Q"), build_ai_message("Answer 1"), build_ai_message("Answer 2")]
        assert get_last_agent_message(msgs) == "Answer 2"

    def test_get_last_agent_message_no_ai_returns_empty(self):
        from memory.conversation_history import build_human_message, get_last_agent_message
        msgs = [build_human_message("Only human message")]
        assert get_last_agent_message(msgs) == ""

    def test_save_messages_to_db(self, db_session, saved_ticket):
        from memory.conversation_history import build_human_message, build_ai_message, save_messages_to_db
        from database.models import Conversation
        msgs = [build_human_message("Hello"), build_ai_message("How can I help?")]
        save_messages_to_db(db_session, saved_ticket.ticket_id, saved_ticket.customer_id, msgs)
        rows = db_session.query(Conversation).filter_by(ticket_id=saved_ticket.ticket_id).all()
        assert len(rows) == 2
        roles = {r.role for r in rows}
        assert "customer" in roles
        assert "agent" in roles

    def test_save_empty_messages_is_noop(self, db_session, saved_ticket):
        from memory.conversation_history import save_messages_to_db
        from database.models import Conversation
        save_messages_to_db(db_session, saved_ticket.ticket_id, saved_ticket.customer_id, [])
        rows = db_session.query(Conversation).filter_by(ticket_id=saved_ticket.ticket_id).all()
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# customer_history
# ---------------------------------------------------------------------------


class TestCustomerHistory:
    def test_get_customer_history_new_customer(self, db_session):
        from memory.customer_history import get_customer_history
        history = get_customer_history(db_session, "CUST-BRAND-NEW")
        assert history.customer_id == "CUST-BRAND-NEW"
        assert history.total_tickets == 0
        assert history.previous_escalations == 0
        assert history.previous_refunds == 0

    def test_get_customer_history_with_ticket(self, db_session, saved_ticket):
        from memory.customer_history import get_customer_history
        history = get_customer_history(db_session, saved_ticket.customer_id)
        assert history.total_tickets == 1
        assert len(history.tickets) == 1

    def test_get_customer_history_counts_escalations(self, db_session, saved_ticket):
        from memory.customer_history import get_customer_history
        escalation = Escalation(
            ticket_id=saved_ticket.ticket_id,
            reason="GDPR request",
            confidence_score=0.95,
        )
        db_session.add(escalation)
        db_session.commit()
        history = get_customer_history(db_session, saved_ticket.customer_id)
        assert history.previous_escalations == 1

    def test_get_customer_history_counts_refunds(self, db_session, saved_ticket):
        from memory.customer_history import get_customer_history
        from memory.long_term_memory import update_ticket_classification
        update_ticket_classification(db_session, saved_ticket.ticket_id, "Refund", 0.9)
        history = get_customer_history(db_session, saved_ticket.customer_id)
        assert history.previous_refunds == 1


# ---------------------------------------------------------------------------
# ticket_memory
# ---------------------------------------------------------------------------


class TestTicketMemory:
    def test_upsert_ticket_creates_row(self, db_session, sample_ticket):
        from memory.ticket_memory import upsert_ticket
        ticket = upsert_ticket(db_session, sample_ticket)
        assert ticket.ticket_id == sample_ticket.ticket_id

    def test_update_ticket_outcome_sets_fields(self, db_session, saved_ticket):
        from memory.ticket_memory import update_ticket_outcome
        from memory.long_term_memory import get_ticket_by_id
        update_ticket_outcome(
            db_session,
            ticket_id=saved_ticket.ticket_id,
            classification="Refund",
            confidence_score=0.88,
            routing_decision="Billing Team",
            escalation_required=False,
        )
        updated = get_ticket_by_id(db_session, saved_ticket.ticket_id)
        assert updated.classification == "Refund"
        assert updated.status == "resolved"

    def test_update_ticket_outcome_escalated_sets_status(self, db_session, saved_ticket):
        from memory.ticket_memory import update_ticket_outcome
        from memory.long_term_memory import get_ticket_by_id
        update_ticket_outcome(
            db_session,
            ticket_id=saved_ticket.ticket_id,
            classification="Billing",
            confidence_score=0.5,
            routing_decision="Human Review Queue",
            escalation_required=True,
        )
        updated = get_ticket_by_id(db_session, saved_ticket.ticket_id)
        assert updated.status == "escalated"

    def test_update_ticket_outcome_unknown_returns_none(self, db_session):
        from memory.ticket_memory import update_ticket_outcome
        result = update_ticket_outcome(db_session, "NOPE", "Billing", 0.5, "Team", False)
        assert result is None

    def test_log_agent_decision_creates_log_row(self, db_session, saved_ticket):
        from memory.ticket_memory import log_agent_decision
        from database.models import AgentLog
        log_agent_decision(
            db_session,
            ticket_id=saved_ticket.ticket_id,
            classification="Refund",
            confidence_score=0.9,
            routing_decision="Billing Team",
            escalation_required=False,
            tokens_used=250,
            cost_usd=0.002,
        )
        rows = db_session.query(AgentLog).filter_by(ticket_id=saved_ticket.ticket_id).all()
        assert len(rows) == 1
        assert rows[0].tokens_used == 250

    def test_save_escalation_creates_escalation_row(self, db_session, saved_ticket):
        from memory.ticket_memory import save_escalation
        esc = save_escalation(db_session, saved_ticket.ticket_id, "Fraud detected", 0.95)
        assert esc.ticket_id == saved_ticket.ticket_id
        assert esc.reason == "Fraud detected"


# ---------------------------------------------------------------------------
# memory_retriever
# ---------------------------------------------------------------------------


class TestMemoryRetriever:
    def test_retrieve_memory_context_returns_memory_context(self, db_session, ephemeral_chroma, sample_ticket):
        from memory.memory_retriever import retrieve_memory_context
        from memory.long_term_memory import save_ticket
        save_ticket(db_session, sample_ticket)
        context = retrieve_memory_context(db_session, sample_ticket)
        assert context.customer_history.customer_id == sample_ticket.customer_id

    def test_retrieve_memory_context_similar_cases_empty_when_no_history(self, db_session, ephemeral_chroma, sample_ticket):
        from memory.memory_retriever import retrieve_memory_context
        from memory.long_term_memory import save_ticket
        from rag.vector_store import delete_collection, TICKETS_COLLECTION
        delete_collection(TICKETS_COLLECTION)  # clear any state from prior tests
        save_ticket(db_session, sample_ticket)
        context = retrieve_memory_context(db_session, sample_ticket)
        assert context.similar_cases == []

    def test_retrieve_memory_context_similarity_score_in_range(self, db_session, ephemeral_chroma, sample_ticket):
        from memory.memory_retriever import retrieve_memory_context
        from memory.long_term_memory import save_ticket
        from memory.semantic_memory import index_ticket
        save_ticket(db_session, sample_ticket)
        index_ticket("TKT-HIST-1", "Annual subscription refund request.", {"classification": "Refund"})
        context = retrieve_memory_context(db_session, sample_ticket)
        for case in context.similar_cases:
            assert 0.0 <= case.similarity_score <= 1.0


# ---------------------------------------------------------------------------
# memory_manager
# ---------------------------------------------------------------------------


class TestMemoryManager:
    def test_load_memory_returns_memory_context(self, db_session, ephemeral_chroma, sample_ticket):
        from memory.memory_manager import load_memory
        context = load_memory(db_session, sample_ticket)
        assert context.customer_history.customer_id == sample_ticket.customer_id

    def test_load_memory_creates_ticket_in_db(self, db_session, ephemeral_chroma, sample_ticket):
        from memory.memory_manager import load_memory
        from memory.long_term_memory import get_ticket_by_id
        load_memory(db_session, sample_ticket)
        ticket = get_ticket_by_id(db_session, sample_ticket.ticket_id)
        assert ticket is not None

    def test_save_memory_writes_agent_log(self, db_session, ephemeral_chroma, sample_ticket):
        from memory.memory_manager import load_memory, save_memory
        from database.models import AgentLog
        load_memory(db_session, sample_ticket)
        state = {
            "ticket": sample_ticket,
            "classification": "Refund",
            "confidence_score": 0.92,
            "routing_decision": "Billing Team",
            "escalation_required": False,
            "escalation_reason": "",
            "audit_log": {"tokens_used": 300, "cost_usd": 0.003, "processing_time_ms": 1200},
            "langfuse_trace_id": None,
            "messages": [],
        }
        save_memory(db_session, state)
        logs = db_session.query(AgentLog).filter_by(ticket_id=sample_ticket.ticket_id).all()
        assert len(logs) == 1
        assert logs[0].tokens_used == 300

    def test_save_memory_writes_escalation_when_required(self, db_session, ephemeral_chroma, sample_ticket):
        from memory.memory_manager import load_memory, save_memory
        from database.models import Escalation as EscalationModel
        load_memory(db_session, sample_ticket)
        state = {
            "ticket": sample_ticket,
            "classification": "Billing",
            "confidence_score": 0.4,
            "routing_decision": "Human Review Queue",
            "escalation_required": True,
            "escalation_reason": "Fraud keywords detected",
            "audit_log": {},
            "langfuse_trace_id": None,
            "messages": [],
        }
        save_memory(db_session, state)
        escs = db_session.query(EscalationModel).filter_by(ticket_id=sample_ticket.ticket_id).all()
        assert len(escs) == 1
        assert "Fraud" in escs[0].reason

    def test_save_memory_no_escalation_when_not_required(self, db_session, ephemeral_chroma, sample_ticket):
        from memory.memory_manager import load_memory, save_memory
        from database.models import Escalation as EscalationModel
        load_memory(db_session, sample_ticket)
        state = {
            "ticket": sample_ticket,
            "classification": "General Inquiry",
            "confidence_score": 0.88,
            "routing_decision": "Customer Success Team",
            "escalation_required": False,
            "escalation_reason": "",
            "audit_log": {},
            "langfuse_trace_id": None,
            "messages": [],
        }
        save_memory(db_session, state)
        escs = db_session.query(EscalationModel).filter_by(ticket_id=sample_ticket.ticket_id).all()
        assert len(escs) == 0
