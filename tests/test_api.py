"""Tests for the FastAPI backend (Phase 10).

All tests use FastAPI's TestClient with:
  - An in-memory SQLite database (overrides get_db) using StaticPool so all
    sessions share the same connection and see each other's tables/rows.
  - A MagicMock graph so no LLM calls happen.
  - Tool functions patched where needed.
"""
from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Shared in-memory test database (StaticPool = all sessions see same data)
# ---------------------------------------------------------------------------

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(bind=_test_engine, autoflush=False, autocommit=False)


def _init_db():
    """Create all tables once."""
    from database.db import Base   # noqa: PLC0415
    import database.models         # noqa: F401, PLC0415
    Base.metadata.create_all(bind=_test_engine)


def _get_test_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


_seeded = False


def _seed_once():
    """Insert CUST-001 / TKT-001 / AgentLog (idempotent)."""
    global _seeded
    if _seeded:
        return
    from database.models import Customer, Ticket, AgentLog  # noqa: PLC0415

    db = _TestSessionLocal()
    try:
        if not db.query(Customer).filter_by(customer_id="CUST-001").first():
            db.add(Customer(
                customer_id="CUST-001", name="Alice Test",
                email="alice@example.com",
                created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
            ))
        if not db.query(Ticket).filter_by(ticket_id="TKT-001").first():
            db.add(Ticket(
                ticket_id="TKT-001", customer_id="CUST-001",
                subject="Wrong charge on my account",
                message="I was charged twice in January.",
                channel="email", priority="medium",
                classification="Billing", confidence_score=0.93,
                status="open",
                created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
            ))
        if not db.query(AgentLog).filter_by(ticket_id="TKT-001").first():
            db.add(AgentLog(
                ticket_id="TKT-001", classification="Billing",
                confidence_score=0.93, routing_decision="Billing Team",
                escalation_required=False, tokens_used=200,
                cost_usd=0.0002, processing_time_ms=320,
            ))
        db.commit()
        _seeded = True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mock_graph():
    g = MagicMock()
    g.invoke.return_value = {
        "classification": "Billing",
        "confidence_score": 0.92,
        "draft_response": "Thank you for reaching out. We will look into your billing issue.",
        "routing_decision": "Billing Team",
        "escalation_required": False,
        "escalation_reason": "",
        "escalation_payload": {},
        "summary": "Customer billed twice; routed to Billing Team.",
        "langfuse_trace_id": "trace-abc123",
        "audit_log": {"total_tokens": 250, "total_cost_usd": 0.00025},
        "messages": [], "customer_history": [],
        "similar_cases": [], "retrieved_policies": [],
    }
    return g


@pytest.fixture(scope="module")
def client(mock_graph):
    """Module-scoped TestClient: shared DB + seeded rows + mock graph."""
    _init_db()
    _seed_once()

    with patch("agents.graph.build_graph", return_value=mock_graph):
        from main import app                       # noqa: PLC0415
        from database.session import get_db        # noqa: PLC0415
        from fastapi.testclient import TestClient  # noqa: PLC0415

        app.dependency_overrides[get_db] = _get_test_db
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


@pytest.fixture
def seeded_db():
    """Yield a session into the shared test DB (seed already applied)."""
    _init_db()
    _seed_once()
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Common test payload
# ---------------------------------------------------------------------------

_TICKET_PAYLOAD = {
    "ticket_id": "TKT-TEST-001",
    "customer_id": "CUST-TEST-001",
    "subject": "I was charged twice",
    "message": "I see two identical charges for $49.99 on my January statement.",
    "channel": "email",
    "priority": "medium",
}


# ===========================================================================
# Health
# ===========================================================================

class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"
        assert body["version"] == "1.0.0"


# ===========================================================================
# Metrics
# ===========================================================================

class TestMetricsEndpoint:
    def test_metrics_returns_expected_shape(self, client):
        resp = client.get("/metrics/")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_tickets_processed" in body
        assert "total_escalations" in body
        assert "escalation_rate" in body
        assert "average_confidence_score" in body
        assert "total_tokens_used" in body
        assert "total_cost_usd" in body
        assert "tickets_by_classification" in body

    def test_metrics_counts_seeded_data(self, client):
        resp = client.get("/metrics/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_tickets_processed"] >= 1
        assert body["tickets_by_classification"].get("Billing", 0) >= 1


# ===========================================================================
# Analyze
# ===========================================================================

class TestAnalyzeEndpoint:
    def test_analyze_happy_path(self, client, mock_graph):
        resp = client.post("/tickets/analyze", json=_TICKET_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticket_id"] == _TICKET_PAYLOAD["ticket_id"]
        assert body["classification"] == "Billing"
        assert body["confidence_score"] == pytest.approx(0.92)
        assert body["escalated"] is False
        assert "response" in body
        assert "routing_decision" in body
        assert "summary" in body
        assert body["tokens_used"] == 250
        assert body["cost_usd"] == pytest.approx(0.00025)
        assert body["langfuse_trace_url"] is not None
        assert "trace-abc123" in body["langfuse_trace_url"]

    def test_analyze_escalated_ticket(self, client, mock_graph):
        orig = dict(mock_graph.invoke.return_value)
        mock_graph.invoke.return_value = {
            **orig,
            "escalation_required": True,
            "escalation_reason": "High-value refund request",
        }
        try:
            resp = client.post("/tickets/analyze", json=_TICKET_PAYLOAD)
            assert resp.status_code == 200
            body = resp.json()
            assert body["escalated"] is True
            assert body["escalation_reason"] == "High-value refund request"
        finally:
            mock_graph.invoke.return_value = orig

    def test_analyze_missing_required_field_returns_422(self, client):
        resp = client.post("/tickets/analyze", json={"subject": "only subject"})
        assert resp.status_code == 422

    def test_analyze_graph_invoked_with_empty_state(self, client, mock_graph):
        mock_graph.invoke.reset_mock()
        client.post("/tickets/analyze", json=_TICKET_PAYLOAD)
        mock_graph.invoke.assert_called_once()
        state = mock_graph.invoke.call_args[0][0]
        assert state["classification"] == ""
        assert state["escalation_required"] is False
        assert state["ticket"].ticket_id == _TICKET_PAYLOAD["ticket_id"]


# ===========================================================================
# Classify
# ===========================================================================

class TestClassifyEndpoint:
    def test_classify_mocked_tool(self, client):
        mock_result = {"classification": "Technical Support", "confidence_score": 0.88}
        with patch("tools.classify_ticket_tool.classify_ticket") as mock_tool:
            mock_tool.invoke.return_value = mock_result
            resp = client.post("/tickets/classify", json=_TICKET_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["classification"] == "Technical Support"

    def test_classify_missing_subject_returns_422(self, client):
        resp = client.post("/tickets/classify", json={"message": "Help me"})
        assert resp.status_code == 422


# ===========================================================================
# Respond
# ===========================================================================

class TestRespondEndpoint:
    _BODY = {
        "subject": "Refund request",
        "message": "I need a refund for order #1234.",
        "classification": "Billing",
        "policy_context": "Refunds processed within 5-7 business days.",
    }

    def test_respond_mocked_tool(self, client):
        mock_result = {
            "draft": "We have received your refund request.",
            "tokens_used": 120,
            "cost_usd": 0.00012,
        }
        with patch("tools.draft_response_tool.draft_response") as mock_tool:
            mock_tool.invoke.return_value = mock_result
            resp = client.post("/tickets/respond", json=self._BODY)
        assert resp.status_code == 200
        body = resp.json()
        assert "draft" in body or "tokens_used" in body

    def test_respond_missing_classification_returns_422(self, client):
        resp = client.post("/tickets/respond", json={"subject": "x", "message": "y"})
        assert resp.status_code == 422


# ===========================================================================
# Route
# ===========================================================================

class TestRouteEndpoint:
    def test_route_billing(self, client):
        mock_result = {"department": "Billing Team", "routing_reason": "Billing issue"}
        with patch("tools.route_ticket_tool.route_ticket") as mock_tool:
            mock_tool.invoke.return_value = mock_result
            resp = client.post("/tickets/route", json={"classification": "Billing"})
        assert resp.status_code == 200
        assert resp.json()["department"] == "Billing Team"

    def test_route_missing_classification_returns_422(self, client):
        resp = client.post("/tickets/route", json={})
        assert resp.status_code == 422


# ===========================================================================
# History
# ===========================================================================

class TestHistoryEndpoint:
    def test_history_known_customer(self, client):
        resp = client.post("/tickets/history", json={"customer_id": "CUST-001"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["customer_id"] == "CUST-001"
        assert body["total_tickets"] >= 1
        assert any(t["ticket_id"] == "TKT-001" for t in body["tickets"])

    def test_history_unknown_customer_returns_empty(self, client):
        resp = client.post("/tickets/history", json={"customer_id": "CUST-DOES-NOT-EXIST"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_tickets"] == 0
        assert body["tickets"] == []

    def test_history_missing_customer_id_returns_422(self, client):
        resp = client.post("/tickets/history", json={})
        assert resp.status_code == 422


# ===========================================================================
# GET /tickets/{ticket_id}
# ===========================================================================

class TestGetTicketEndpoint:
    def test_get_known_ticket(self, client):
        resp = client.get("/tickets/TKT-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticket_id"] == "TKT-001"
        assert body["customer_id"] == "CUST-001"
        assert body["classification"] == "Billing"

    def test_get_unknown_ticket_returns_404(self, client):
        resp = client.get("/tickets/TKT-DOES-NOT-EXIST")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ===========================================================================
# GET /customers/{customer_id}
# ===========================================================================

class TestGetCustomerEndpoint:
    def test_get_known_customer(self, client):
        resp = client.get("/customers/CUST-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["customer_id"] == "CUST-001"
        assert body["name"] == "Alice Test"
        assert body["email"] == "alice@example.com"
        assert body["total_tickets"] >= 1
        assert any(t["ticket_id"] == "TKT-001" for t in body["recent_tickets"])

    def test_get_unknown_customer_returns_404(self, client):
        resp = client.get("/customers/CUST-DOES-NOT-EXIST")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
