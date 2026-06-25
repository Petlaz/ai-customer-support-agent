"""Tests for database/crud.py (Phase 11).

All tests use an in-memory SQLite database with StaticPool so every session
shares the same connection and tables are visible across sessions.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Test DB setup
# ---------------------------------------------------------------------------

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="module", autouse=True)
def _init_db():
    from database.db import Base  # noqa: PLC0415
    import database.models        # noqa: F401, PLC0415
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db():
    session = _Session()
    try:
        yield session
    finally:
        session.close()


# ===========================================================================
# Customer
# ===========================================================================

class TestGetOrCreateCustomer:
    def test_creates_new_customer(self, db):
        from database import crud  # noqa: PLC0415
        c = crud.get_or_create_customer(db, "CUST-NEW-1")
        assert c.customer_id == "CUST-NEW-1"
        assert c.id is not None

    def test_idempotent_second_call(self, db):
        from database import crud  # noqa: PLC0415
        c1 = crud.get_or_create_customer(db, "CUST-IDEM-1")
        c2 = crud.get_or_create_customer(db, "CUST-IDEM-1")
        assert c1.id == c2.id

    def test_stores_email_and_name(self, db):
        from database import crud  # noqa: PLC0415
        c = crud.get_or_create_customer(db, "CUST-META-1", email="a@b.com", name="Alice")
        assert c.email == "a@b.com"
        assert c.name == "Alice"


class TestGetCustomer:
    def test_returns_existing_customer(self, db):
        from database import crud  # noqa: PLC0415
        crud.get_or_create_customer(db, "CUST-GET-1")
        c = crud.get_customer(db, "CUST-GET-1")
        assert c is not None
        assert c.customer_id == "CUST-GET-1"

    def test_returns_none_for_missing(self, db):
        from database import crud  # noqa: PLC0415
        assert crud.get_customer(db, "CUST-MISSING") is None


# ===========================================================================
# Ticket
# ===========================================================================

_TICKET_DEFAULTS = dict(
    customer_id="CUST-TKT-1",
    subject="Test subject",
    message="Test message body",
    channel="email",
    priority="medium",
)


class TestCreateTicket:
    def test_creates_ticket(self, db):
        from database import crud  # noqa: PLC0415
        t = crud.create_ticket(db, ticket_id="TKT-C-1", **_TICKET_DEFAULTS)
        assert t.ticket_id == "TKT-C-1"
        assert t.status == "open"
        assert t.id is not None

    def test_idempotent_on_duplicate_ticket_id(self, db):
        from database import crud  # noqa: PLC0415
        t1 = crud.create_ticket(db, ticket_id="TKT-C-2", **_TICKET_DEFAULTS)
        t2 = crud.create_ticket(db, ticket_id="TKT-C-2", **_TICKET_DEFAULTS)
        assert t1.id == t2.id

    def test_auto_creates_customer_row(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_ticket(db, ticket_id="TKT-C-3", customer_id="CUST-AUTO-1",
                           subject="S", message="M", channel="chat", priority="low")
        assert crud.get_customer(db, "CUST-AUTO-1") is not None

    def test_stores_optional_classification(self, db):
        from database import crud  # noqa: PLC0415
        t = crud.create_ticket(db, ticket_id="TKT-C-4", classification="Billing",
                               confidence_score=0.9, **_TICKET_DEFAULTS)
        assert t.classification == "Billing"
        assert t.confidence_score == pytest.approx(0.9)


class TestGetTicket:
    def test_returns_existing_ticket(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_ticket(db, ticket_id="TKT-G-1", **_TICKET_DEFAULTS)
        t = crud.get_ticket(db, "TKT-G-1")
        assert t is not None
        assert t.ticket_id == "TKT-G-1"

    def test_returns_none_for_missing(self, db):
        from database import crud  # noqa: PLC0415
        assert crud.get_ticket(db, "TKT-MISSING") is None


class TestUpdateTicketClassification:
    def test_updates_classification(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_ticket(db, ticket_id="TKT-U-1", **_TICKET_DEFAULTS)
        t = crud.update_ticket_classification(db, "TKT-U-1", "Billing", 0.95)
        assert t.classification == "Billing"
        assert t.confidence_score == pytest.approx(0.95)

    def test_returns_none_for_missing_ticket(self, db):
        from database import crud  # noqa: PLC0415
        assert crud.update_ticket_classification(db, "TKT-NONE", "Billing", 0.9) is None


class TestUpdateTicketStatus:
    def test_updates_status(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_ticket(db, ticket_id="TKT-S-1", **_TICKET_DEFAULTS)
        t = crud.update_ticket_status(db, "TKT-S-1", "resolved")
        assert t.status == "resolved"

    def test_returns_none_for_missing_ticket(self, db):
        from database import crud  # noqa: PLC0415
        assert crud.update_ticket_status(db, "TKT-NONE", "resolved") is None


class TestGetCustomerHistory:
    def test_returns_tickets_newest_first(self, db):
        from database import crud  # noqa: PLC0415
        from datetime import datetime, timedelta  # noqa: PLC0415
        from database.models import Ticket  # noqa: PLC0415

        crud.get_or_create_customer(db, "CUST-HIST-1")
        for i in range(3):
            db.add(Ticket(
                ticket_id=f"TKT-HIST-1-{i}",
                customer_id="CUST-HIST-1",
                subject=f"Subject {i}",
                message="msg",
                channel="email",
                priority="low",
            ))
        db.commit()

        history = crud.get_customer_history(db, "CUST-HIST-1", limit=10)
        assert len(history) == 3
        # All belong to the customer
        assert all(t.customer_id == "CUST-HIST-1" for t in history)

    def test_respects_limit(self, db):
        from database import crud  # noqa: PLC0415
        crud.get_or_create_customer(db, "CUST-HIST-2")
        from database.models import Ticket  # noqa: PLC0415
        for i in range(5):
            db.add(Ticket(
                ticket_id=f"TKT-HIST-2-{i}",
                customer_id="CUST-HIST-2",
                subject="S", message="M", channel="email", priority="low",
            ))
        db.commit()
        assert len(crud.get_customer_history(db, "CUST-HIST-2", limit=2)) == 2

    def test_returns_empty_for_unknown_customer(self, db):
        from database import crud  # noqa: PLC0415
        assert crud.get_customer_history(db, "CUST-NO-TICKETS") == []


# ===========================================================================
# Escalation
# ===========================================================================

class TestCreateEscalation:
    def test_creates_escalation(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_ticket(db, ticket_id="TKT-ESC-1", **_TICKET_DEFAULTS)
        e = crud.create_escalation(db, ticket_id="TKT-ESC-1",
                                   reason="High-value refund", confidence_score=0.55)
        assert e.ticket_id == "TKT-ESC-1"
        assert e.reason == "High-value refund"
        assert e.resolved is False
        assert e.id is not None

    def test_resolved_by_can_be_set(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_ticket(db, ticket_id="TKT-ESC-2", **_TICKET_DEFAULTS)
        e = crud.create_escalation(db, ticket_id="TKT-ESC-2",
                                   reason="Keyword match", confidence_score=0.6,
                                   resolved=True, resolved_by="agent-42")
        assert e.resolved is True
        assert e.resolved_by == "agent-42"


class TestGetEscalation:
    def test_returns_escalation(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_ticket(db, ticket_id="TKT-ESC-G-1", **_TICKET_DEFAULTS)
        crud.create_escalation(db, ticket_id="TKT-ESC-G-1",
                               reason="Test", confidence_score=0.5)
        e = crud.get_escalation(db, "TKT-ESC-G-1")
        assert e is not None

    def test_returns_none_for_missing(self, db):
        from database import crud  # noqa: PLC0415
        assert crud.get_escalation(db, "TKT-NO-ESC") is None


# ===========================================================================
# AgentLog
# ===========================================================================

class TestCreateAgentLog:
    def test_creates_log(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_ticket(db, ticket_id="TKT-LOG-1", **_TICKET_DEFAULTS)
        log = crud.create_agent_log(
            db,
            ticket_id="TKT-LOG-1",
            classification="Billing",
            confidence_score=0.93,
            routing_decision="Billing Team",
            escalation_required=False,
            tokens_used=300,
            cost_usd=0.0003,
            processing_time_ms=420,
        )
        assert log.ticket_id == "TKT-LOG-1"
        assert log.classification == "Billing"
        assert log.tokens_used == 300
        assert log.id is not None

    def test_defaults_are_safe(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_ticket(db, ticket_id="TKT-LOG-2", **_TICKET_DEFAULTS)
        log = crud.create_agent_log(db, ticket_id="TKT-LOG-2")
        assert log.tokens_used == 0
        assert log.escalation_required is False

    def test_langfuse_trace_id_stored(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_ticket(db, ticket_id="TKT-LOG-3", **_TICKET_DEFAULTS)
        log = crud.create_agent_log(db, ticket_id="TKT-LOG-3",
                                    langfuse_trace_id="trace-xyz")
        assert log.langfuse_trace_id == "trace-xyz"


# ===========================================================================
# EvaluationResult
# ===========================================================================

class TestCreateEvaluationResult:
    def test_creates_result(self, db):
        from database import crud  # noqa: PLC0415
        result = crud.create_evaluation_result(
            db,
            case_id="CASE-1",
            ticket_id="TKT-EVAL-1",
            classification_correct=True,
            routing_correct=True,
            escalation_correct=False,
            confidence_score=0.88,
            processing_time_ms=500,
            tokens_used=200,
            cost_usd=0.0002,
        )
        assert result.case_id == "CASE-1"
        assert result.classification_correct is True
        assert result.routing_correct is True
        assert result.escalation_correct is False
        assert result.id is not None

    def test_langfuse_trace_id_stored(self, db):
        from database import crud  # noqa: PLC0415
        result = crud.create_evaluation_result(
            db,
            case_id="CASE-2",
            ticket_id="TKT-EVAL-2",
            classification_correct=True,
            routing_correct=False,
            escalation_correct=True,
            confidence_score=0.72,
            langfuse_trace_id="trace-eval-001",
        )
        assert result.langfuse_trace_id == "trace-eval-001"


class TestGetEvaluationResults:
    def test_returns_all_results(self, db):
        from database import crud  # noqa: PLC0415
        for i in range(3):
            crud.create_evaluation_result(
                db,
                case_id=f"CASE-LIST-{i}",
                ticket_id=f"TKT-EVAL-LIST-{i}",
                classification_correct=True,
                routing_correct=True,
                escalation_correct=True,
                confidence_score=0.9,
            )
        results = crud.get_evaluation_results(db)
        assert len(results) >= 3

    def test_filters_by_ticket_id(self, db):
        from database import crud  # noqa: PLC0415
        crud.create_evaluation_result(
            db, case_id="CASE-FILTER-1", ticket_id="TKT-FILTER-UNIQUE",
            classification_correct=True, routing_correct=True,
            escalation_correct=True, confidence_score=0.85,
        )
        results = crud.get_evaluation_results(db, ticket_id="TKT-FILTER-UNIQUE")
        assert len(results) == 1
        assert results[0].ticket_id == "TKT-FILTER-UNIQUE"

    def test_returns_empty_for_unknown_ticket(self, db):
        from database import crud  # noqa: PLC0415
        assert crud.get_evaluation_results(db, ticket_id="TKT-NOT-EVAL") == []
