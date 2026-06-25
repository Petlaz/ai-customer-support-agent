# REST API Reference

Base URL (local): `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs` (Swagger UI) · `http://localhost:8000/redoc`

---

## Authentication

Not required for local development. Production deployments should add a JWT/API-key middleware layer (see `security/auth.py`).

---

## Endpoints

### Health

#### `GET /health`

Liveness check. Returns `200 OK` when the API and database are reachable.

**Response `200`**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "ok"
}
```

---

### Metrics

#### `GET /metrics/`

Returns aggregate statistics from the `agent_logs` table.

**Response `200`**
```json
{
  "total_tickets_processed": 142,
  "total_escalations": 18,
  "escalation_rate": 0.1268,
  "average_confidence_score": 0.8714,
  "total_tokens_used": 38450,
  "total_cost_usd": 0.038512,
  "tickets_by_classification": {
    "Billing": 47,
    "Technical Support": 38,
    "Refund": 29,
    "Account": 28
  }
}
```

---

### Tickets

#### `POST /tickets/analyze`

Runs a ticket through the **full LangGraph agent pipeline**: retrieve memory → classify → retrieve policy → draft response → check confidence → route or escalate → summarise → store → log.

This is the primary integration endpoint.

**Request body**
```json
{
  "ticket_id": "TKT-2024-001",
  "customer_id": "CUST-42",
  "subject": "Charged twice this month",
  "message": "I see two identical charges of $49.99 on my January statement. Please investigate.",
  "channel": "email",
  "priority": "medium"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `ticket_id` | string | ✅ | Unique ticket identifier |
| `customer_id` | string | ✅ | Customer identifier |
| `subject` | string | ✅ | Short subject line |
| `message` | string | ✅ | Full message body |
| `channel` | string | ✅ | `email`, `chat`, `phone`, `api` |
| `priority` | string | ✅ | `low`, `medium`, `high`, `urgent` |
| `created_at` | datetime | ❌ | ISO 8601; defaults to now |

**Response `200`**
```json
{
  "ticket_id": "TKT-2024-001",
  "classification": "Billing",
  "confidence_score": 0.94,
  "response": "Thank you for reaching out. I can see two charges of $49.99 on your account for January. Our billing team will investigate and issue a refund for the duplicate within 3–5 business days. You will receive a confirmation email once it is processed.",
  "routing_decision": "Billing Team",
  "escalated": false,
  "escalation_reason": null,
  "summary": "Customer reported a duplicate billing charge of $49.99 in January. Routed to Billing Team for investigation and refund.",
  "langfuse_trace_url": "https://cloud.langfuse.com/traces/trace-abc123",
  "processing_time_ms": 1842,
  "tokens_used": 487,
  "cost_usd": 0.000292
}
```

| Field | Type | Notes |
|-------|------|-------|
| `ticket_id` | string | Echoed from request |
| `classification` | string | e.g. `Billing`, `Technical Support`, `Refund`, `Account` |
| `confidence_score` | float | `0.0`–`1.0` |
| `response` | string | Drafted customer-facing response |
| `routing_decision` | string | Target department |
| `escalated` | bool | `true` if routed to human review |
| `escalation_reason` | string\|null | Set when `escalated=true` |
| `summary` | string | One-sentence agent summary |
| `langfuse_trace_url` | string\|null | Full observability trace link |
| `processing_time_ms` | int | Wall-clock time for full pipeline |
| `tokens_used` | int | Total tokens consumed |
| `cost_usd` | float | Estimated OpenAI cost |

**Error `422`** — validation failure (missing required fields).

---

#### `POST /tickets/classify`

Classifies a ticket using `classify_ticket_tool` only. No response drafting, no memory writes. Faster than `/analyze`.

**Request body** — same shape as `/tickets/analyze`

**Response `200`**
```json
{
  "classification": "Technical Support",
  "confidence_score": 0.88,
  "reasoning": "Ticket describes a login error, which maps to Technical Support."
}
```

**Error `422`** — missing `subject` or `message`.

---

#### `POST /tickets/respond`

Drafts a customer response using `draft_response_tool`. The caller supplies the pre-classified category and any retrieved policy context — useful when you want fine-grained control over what the model sees.

**Request body**
```json
{
  "subject": "Refund request for cancelled subscription",
  "message": "I cancelled my subscription on Jan 3rd but was still charged on Jan 5th.",
  "classification": "Refund",
  "policy_context": "Refunds for cancelled subscriptions are processed within 5–7 business days of the cancellation date.",
  "similar_cases": "",
  "customer_history": ""
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `subject` | string | ✅ | |
| `message` | string | ✅ | |
| `classification` | string | ✅ | Pre-determined ticket category |
| `policy_context` | string | ❌ | Pre-retrieved policy text |
| `similar_cases` | string | ❌ | Formatted similar case context |
| `customer_history` | string | ❌ | Formatted prior ticket history |

**Response `200`**
```json
{
  "draft": "Thank you for contacting us. I can confirm that a refund for your January 5th charge has been initiated. As per our refund policy, you will see the credit within 5–7 business days.",
  "tokens_used": 214,
  "cost_usd": 0.000128
}
```

**Error `422`** — missing `subject`, `message`, or `classification`.

---

#### `POST /tickets/route`

Maps a ticket classification string to the handling department. Pure lookup — no DB or LLM calls.

**Request body**
```json
{
  "classification": "Billing"
}
```

**Response `200`**
```json
{
  "department": "Billing Team",
  "routing_reason": "Ticket classified as Billing"
}
```

**Error `422`** — missing `classification`.

---

#### `POST /tickets/history`

Retrieves the prior ticket history for a customer from the database.

**Request body**
```json
{
  "customer_id": "CUST-42",
  "limit": 10
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `customer_id` | string | ✅ | |
| `limit` | int | ❌ | Default `10` |

**Response `200`** *(empty if customer not found — not a 404)*
```json
{
  "customer_id": "CUST-42",
  "tickets": [
    {
      "ticket_id": "TKT-2023-088",
      "subject": "Billing discrepancy",
      "classification": "Billing",
      "status": "resolved",
      "created_at": "2023-12-14T09:22:01"
    }
  ],
  "total_tickets": 1,
  "previous_escalations": 0
}
```

**Error `422`** — missing `customer_id`.

---

#### `GET /tickets/{ticket_id}`

Fetches a stored ticket record by its ID.

**Path parameter:** `ticket_id` — e.g. `TKT-2024-001`

**Response `200`**
```json
{
  "ticket_id": "TKT-2024-001",
  "customer_id": "CUST-42",
  "subject": "Charged twice this month",
  "classification": "Billing",
  "confidence_score": 0.94,
  "status": "open",
  "channel": "email",
  "priority": "medium",
  "created_at": "2024-01-15T14:03:22"
}
```

**Error `404`** — ticket not found.
```json
{ "detail": "Ticket 'TKT-XXXX' not found" }
```

---

### Customers

#### `GET /customers/{customer_id}`

Fetches a customer record with their most recent 20 tickets.

**Path parameter:** `customer_id` — e.g. `CUST-42`

**Response `200`**
```json
{
  "customer_id": "CUST-42",
  "name": "Jane Smith",
  "email": "jane@example.com",
  "created_at": "2023-06-01T10:00:00",
  "total_tickets": 3,
  "recent_tickets": [
    {
      "ticket_id": "TKT-2024-001",
      "subject": "Charged twice this month",
      "classification": "Billing",
      "status": "open",
      "created_at": "2024-01-15T14:03:22"
    }
  ]
}
```

**Error `404`** — customer not found.
```json
{ "detail": "Customer 'CUST-XXXX' not found" }
```

---

## Error Format

All `4xx` errors use FastAPI's standard detail envelope:

```json
{ "detail": "Human-readable error message" }
```

Validation errors (`422`) include a structured breakdown:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "classification"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

---

## Running locally

```bash
uvicorn main:app --reload --port 8000
```

Or via Docker Compose:

```bash
docker compose up --build
```

---

## Request / Response Schemas

All Pydantic schemas live in `api/schemas/`:

| File | Models |
|------|--------|
| `ticket_schema.py` | `TicketInput`, `TicketResponse` |
| `response_schema.py` | `SuccessResponse`, `ErrorResponse`, `PaginatedResponse` |
| `routing_schema.py` | `RoutingDecision`, `RoutingRequest` |
| `escalation_schema.py` | `EscalationTrigger`, `EscalationPayload`, `EscalationRequest`, `EscalationReview` |
| `memory_schema.py` | `PreviousTicket`, `CustomerHistory`, `SimilarCase`, `MemoryContext` |
| `evaluation_schema.py` | `EvaluationResult` |
