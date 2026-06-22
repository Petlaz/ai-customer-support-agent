# AI Customer Support Automation Agent
## Project Requirements Specification (PRS)

---

## Project Overview

This project aims to build a production-grade **Agentic AI Customer Support Automation Platform** that automates customer support workflows using Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), LangGraph, Memory Systems, Tool Calling, Langfuse Observability, and Apache Airflow Orchestration.

The system should intelligently process customer support requests, retrieve relevant company knowledge, retrieve customer history and similar historical cases, generate grounded responses, route tickets to the correct department, and escalate complex cases to human support agents when necessary.

The project is intended to demonstrate real-world AI Engineering concepts including:

- Agentic AI
- LangGraph Workflows
- Retrieval-Augmented Generation (RAG)
- Tool Calling
- Short-Term Memory
- Long-Term Memory
- Semantic Memory
- Human-in-the-Loop Systems
- Evaluation Frameworks
- Langfuse Observability
- Apache Airflow Orchestration
- FastAPI
- Docker
- AWS Deployment
- Terraform
- CI/CD
- Monitoring and Observability

---

## Business Problem

Customer support teams spend a significant amount of time handling repetitive customer inquiries.

For every support request, a human agent typically needs to:

1. Read the customer message
2. Understand customer intent
3. Determine issue category
4. Search internal documentation
5. Search previous customer history
6. Search similar historical cases
7. Draft an appropriate response
8. Route the ticket to the correct department
9. Escalate complex cases when necessary

As ticket volume grows, organizations face:

- Long response times
- Increased support costs
- Inconsistent responses
- Agent burnout
- Reduced customer satisfaction

Traditional chatbots can answer simple questions but cannot reliably:

- Perform multi-step reasoning
- Retrieve company knowledge
- Retrieve customer history
- Search similar historical cases
- Use tools
- Make routing decisions
- Decide when human intervention is required
- Maintain auditable decision traces

---

## Project Goal

Build an AI-powered support agent capable of automating the majority of customer support workflows while maintaining **transparency, reliability, auditability, observability, and human oversight**.

The system should behave similarly to a junior customer support representative that:

- Follows company policies
- Uses previous customer interactions
- Learns from historical resolutions
- Understands customer context
- Knows when to escalate issues

---

## Primary Objectives

### 1. Classify Customer Tickets

Supported categories:

- Billing
- Refund
- Technical Support
- Account Access
- Product Questions
- General Inquiries

### 2. Retrieve Company Knowledge

Use RAG to search:

- FAQ documents
- Billing policies
- Refund policies
- Product documentation
- Troubleshooting guides
- Internal support procedures

The system must generate grounded responses using retrieved context.

### 3. Retrieve Customer Memory

Retrieve customer-specific information such as:

- Previous tickets
- Previous refunds
- Previous escalations
- Previous conversations
- Previous resolutions

The agent should use this information when generating responses.

### 4. Retrieve Similar Historical Cases

Search historical ticket data and retrieve:

- Similar tickets
- Similar conversations
- Similar resolutions

The agent should leverage successful historical resolutions as additional context.

### 5. Generate Customer Responses

Responses must:

- Follow company policies
- Use retrieved company knowledge
- Use customer history
- Use similar historical cases
- Avoid hallucinations
- Explain next steps clearly

### 6. Route Tickets Automatically

Supported departments:

- Billing Team
- Technical Support Team
- Customer Success Team
- Product Team
- Human Review Queue

### 7. Escalate Complex Cases

Examples:

- Low confidence
- Missing policy information
- Legal concerns
- Compliance issues
- High-value refunds
- Sensitive customer information
- Ambiguous requests

### 8. Summarize Tickets

Example:

> Customer reports duplicate payment and requests refund. Refund policy retrieved successfully. Previous refund request found. Similar historical case retrieved. Ticket routed to Billing Team.

### 9. Maintain Audit Logs

Record:

- User query
- Classification result
- Retrieved documents
- Retrieved memories
- Retrieved similar cases
- Draft response
- Routing decision
- Escalation decision
- Confidence score
- Processing time
- LLM usage
- Token usage
- Cost

---

## Memory Requirements

### Short-Term Memory

**Purpose:** Maintain context during the current ticket conversation.

**Store:**
- Conversation history
- Previous customer messages
- Previous agent responses
- Ticket state
- Workflow state

**Implementation:** LangGraph State

---

### Long-Term Memory

**Purpose:** Remember customer interactions across sessions.

**Store:**
- Previous tickets
- Previous resolutions
- Previous escalations
- Previous refunds
- Previous conversations

**Implementation:** PostgreSQL

---

### Semantic Memory

**Purpose:** Retrieve similar historical tickets and resolutions.

**Store embeddings for:**
- Historical tickets
- Conversations
- Resolutions

**Implementation:** Chroma Vector Database

---

## Observability Requirements

### Langfuse

The system must integrate Langfuse for:

- LLM tracing
- Prompt tracking
- Tool call tracking
- Retrieval tracing
- Agent workflow tracing
- Token monitoring
- Cost monitoring
- Evaluation tracking
- Prompt version management

All agent executions must be traceable through Langfuse.

---

## Orchestration Requirements

### Apache Airflow

The system must use Airflow to orchestrate:

**Knowledge Base Pipelines**
- Document ingestion
- Embedding generation
- Vector indexing
- Policy refresh

**Memory Pipelines**
- Historical ticket ingestion
- Resolution ingestion
- Memory indexing

**Evaluation Pipelines**
- Daily evaluations
- Weekly benchmark runs
- Regression testing

**Maintenance Pipelines**
- Cleanup jobs
- Monitoring jobs
- Data quality checks

---

## User Workflow

| Step | Action |
|------|--------|
| 1 | Customer submits a support request |
| 2 | Agent retrieves customer history |
| 3 | Agent retrieves similar historical cases |
| 4 | Agent classifies the ticket |
| 5 | Agent retrieves relevant company policies |
| 6 | Agent drafts a grounded response |
| 7 | Agent determines routing |
| 8 | Agent determines escalation status |
| 9 | Agent generates ticket summary |
| 10 | Agent stores new memory |
| 11 | Agent logs all decisions and traces |

**Example Input:**
> "I was charged twice for my subscription and would like a refund."

---

## Agent Architecture

The system must be implemented using **LangGraph**.

> **Important:** Classification happens *before* policy retrieval. The agent must first understand what category the ticket belongs to, then retrieve the relevant policy for that category. Retrieving all policies upfront would be noisy and expensive.

```
Receive Ticket
      ↓
Retrieve Long-Term Memory       ← Who is this customer? Any previous tickets/refunds?
      ↓
Retrieve Semantic Memory        ← Any similar historical cases with known resolutions?
      ↓
Classify Ticket                 ← What category? (Billing / Refund / Technical / etc.)
      ↓
Retrieve Policy                 ← Fetch the relevant policy documents for that category
      ↓
Draft Response                  ← Generate grounded response using policy + memory + history
      ↓
Evaluate Confidence             ← Is the agent confident enough to auto-respond?
      ↓
   [Branch]
   /       \
High       Low Confidence
Confidence  or Escalation Trigger
   |              |
Route Ticket   Escalate to Human Review
   |              |
   └──────┬───────┘
          ↓
    Generate Summary             ← Summarize the ticket, actions taken, routing decision
          ↓
    Store Memory                 ← Persist new interaction to long-term memory (PostgreSQL)
          ↓
    Log Decision                 ← Record full audit trail: query, classification, response,
          ↓                         routing, confidence, tokens, cost
    Trace to Langfuse            ← Ship full trace to Langfuse for observability
          ↓
    Return Final Output
```

### Conditional Edges (LangGraph)

The graph is **not purely linear**. The following conditional edges exist:

| Node | Condition | Next Node |
|------|-----------|----------|
| `check_confidence` | `confidence >= threshold` | `route_ticket` |
| `check_confidence` | `confidence < threshold` OR escalation trigger | `escalate_ticket` |
| `escalate_ticket` | always | `summarize_ticket` |
| `route_ticket` | always | `summarize_ticket` |

---

## Required AI Components

| Layer | Responsibility |
|-------|---------------|
| **LLM Layer** | Classification, Response Generation, Summarization, Decision Support |
| **RAG Layer** | Retrieval, Context Generation, Grounding Responses |
| **Memory Layer** | Conversation Memory, Customer History Retrieval, Similar Case Retrieval |
| **Agent Layer** | Workflow Orchestration, Tool Calling, Routing Decisions, Escalation Decisions |
| **Evaluation Layer** | Measuring Accuracy, Retrieval Quality, Memory Quality, Hallucination Detection, Latency Tracking |
| **Observability Layer** | Tracing, Prompt Monitoring, Cost Monitoring, Token Monitoring, Agent Analytics |
| **Orchestration Layer** | Scheduled Ingestion, Scheduled Evaluation, Scheduled Maintenance |

---

## Key Design Decisions

These decisions explain *why* each technology was chosen over alternatives.

| Decision | Choice | Why |
|----------|--------|-----|
| **Agent Framework** | LangGraph | Provides explicit, stateful, graph-based workflow control with conditional branching — essential for human-in-the-loop and escalation logic. More controllable than pure ReAct agents. |
| **LLM Provider** | OpenAI (primary) | GPT-4o-mini for development (cheap, fast), GPT-4o for production (best accuracy). Most LangGraph examples target OpenAI — fewer integration issues. Anthropic Claude is supported as an optional fallback via `config/settings.py`. |
| **Short-Term Memory** | LangGraph State | Native to the framework; zero infrastructure required; perfectly scoped to a single ticket's lifecycle. |
| **Long-Term Memory** | PostgreSQL | Structured customer history (tickets, refunds, escalations) needs relational queries — vector search is wrong tool here. RDS in production. |
| **Semantic Memory** | ChromaDB | Local-first vector database — runs in-process for development, can be replaced with OpenSearch/Pinecone in production. Best for similar-case retrieval. |
| **RAG** | LangChain + ChromaDB | LangChain's document loaders, text splitters, and retrievers accelerate the RAG pipeline without vendor lock-in. |
| **Observability** | Langfuse | Purpose-built for LLM applications — traces every prompt, tool call, and token. Supports prompt versioning and evaluation scoring. |
| **Orchestration** | Apache Airflow | Industry-standard for scheduled data pipelines (ingestion, indexing, evaluation). DAG-based, auditable, retryable. |
| **API Layer** | FastAPI | Async, type-safe, auto-generates OpenAPI docs. Pydantic integration for request/response validation out of the box. |
| **IaC** | Terraform | Declarative AWS infrastructure. Reproducible, version-controlled, supports modular design for VPC / ECS / RDS / S3. |
| **Frontend** | Gradio | Fastest path to a working demo UI for AI applications without needing a full React/Next.js frontend. |

---

## Key Data Models

These are the core data structures flowing through the system. They map directly to the `api/schemas/` Pydantic models and `database/models.py` SQLAlchemy models.

### TicketInput (incoming request)
```python
class TicketInput(BaseModel):
    ticket_id: str
    customer_id: str
    subject: str
    message: str
    channel: str          # email | chat | api
    priority: str         # low | medium | high
    created_at: datetime
```

### AgentState (LangGraph state — flows through all nodes)
```python
class AgentState(TypedDict):
    ticket: TicketInput
    customer_history: list[dict]       # from long-term memory (PostgreSQL)
    similar_cases: list[dict]          # from semantic memory (ChromaDB)
    classification: str                # Billing | Refund | Technical | etc.
    confidence_score: float            # 0.0 – 1.0
    retrieved_policies: list[str]      # RAG results
    draft_response: str
    routing_decision: str              # Billing Team | Tech Team | etc.
    escalation_required: bool
    escalation_reason: str
    summary: str
    audit_log: dict                    # full decision trace
    langfuse_trace_id: str
```

### TicketResponse (API output)
```python
class TicketResponse(BaseModel):
    ticket_id: str
    classification: str
    confidence_score: float
    response: str
    routing_decision: str
    escalated: bool
    escalation_reason: str | None
    summary: str
    langfuse_trace_url: str
    processing_time_ms: int
    tokens_used: int
    cost_usd: float
```

---

## End-to-End Walkthrough

**Customer message:** *"I was charged twice for my subscription last week and I'd like a refund."*

| Step | Node | What Happens | Output |
|------|------|-------------|--------|
| 1 | `receive_ticket` | Ticket is parsed and validated into `TicketInput`. `AgentState` is initialized. | `ticket` in state |
| 2 | `retrieve_long_term_memory` | PostgreSQL is queried for this customer's history: previous tickets, refunds, escalations. | `customer_history` in state |
| 3 | `retrieve_semantic_memory` | ChromaDB is queried with the ticket embedding to find similar resolved tickets. | `similar_cases` in state |
| 4 | `classify_ticket` | LLM classifies the ticket. Given "charged twice" + "refund", output is **`Refund`** with 0.95 confidence. | `classification = "Refund"` |
| 5 | `retrieve_policy` | RAG retrieves `refund_policy.md` and `billing_policy.md` chunks relevant to duplicate charges. | `retrieved_policies` in state |
| 6 | `draft_response` | LLM generates a response grounded in: policy docs + customer history + similar case resolutions. | `draft_response` in state |
| 7 | `check_confidence` | Confidence = 0.87 ≥ threshold (0.75). No escalation triggers. Proceeds to routing. | `escalation_required = False` |
| 8 | `route_ticket` | LLM decides: classification is Refund → route to **Billing Team**. | `routing_decision = "Billing Team"` |
| 9 | `summarize_ticket` | Summary generated: *"Duplicate charge refund request. Policy retrieved. No prior refund found. Routed to Billing Team."* | `summary` in state |
| 10 | `store_memory` | New ticket + resolution stored in PostgreSQL. Ticket embedding stored in ChromaDB for future similar-case retrieval. | DB updated |
| 11 | `log_decision` | Full audit log written: query, classification, policies retrieved, response, routing, confidence, tokens, cost. | `audit_log` in state |
| 12 | Langfuse | Complete trace shipped: all LLM calls, tool calls, retrieved docs, latency, token counts, cost. | Trace visible in Langfuse UI |
| 13 | Return | `TicketResponse` returned via FastAPI. | Final JSON response |

**If confidence was low (< 0.75) or a legal concern was detected:** Step 8 would become `escalate_ticket` instead — the ticket is flagged for human review with the draft response, retrieved policies, and confidence score attached as context.

---

## Non-Functional Requirements

The system must:

- Be modular
- Be production-ready
- Be containerized with Docker
- Expose REST APIs through FastAPI
- Support AWS deployment
- Support CI/CD
- Support monitoring and logging
- Support Langfuse tracing
- Support Airflow orchestration
- Support structured outputs with Pydantic
- Follow clean architecture principles
- Support auditability and traceability

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Classification Accuracy | ≥ 90% |
| Routing Accuracy | ≥ 90% |
| Policy Retrieval Relevance | ≥ 85% |
| Memory Retrieval Relevance | ≥ 85% |
| Hallucination Rate | ≤ 5% |
| Average Response Latency | < 5 seconds |
| Escalation Precision | ≥ 80% |
| Human Approval Rate | ≥ 85% |
| API Availability | ≥ 99% |

---

## Out of Scope (Version 1)

Do **NOT** implement:

- Voice agents
- Phone call integration
- Multi-agent systems
- Fine-tuning models
- Custom model training
- Knowledge graphs
- Social media integrations
- Multi-language support
- Autonomous decision-making without human oversight

---

## Version 1 Technology Stack

| Category | Technology |
|----------|-----------|
| Agent Framework | LangGraph, LangChain |
| API Layer | FastAPI |
| Relational Database | PostgreSQL |
| Vector Database | ChromaDB |
| LLM APIs | OpenAI GPT-4o (primary) — `gpt-4o-mini` for dev, `gpt-4o` for prod. Anthropic Claude optional fallback. |
| Observability | Langfuse |
| Orchestration | Apache Airflow |
| Containerization | Docker |
| CI/CD | GitHub Actions |
| Infrastructure as Code | Terraform |
| Cloud Compute | AWS ECS Fargate |
| Cloud Database | Amazon RDS |
| Cloud Storage | Amazon S3 |
| Cloud Monitoring | CloudWatch |
| Frontend / Demo UI | Gradio |

---

## Recommended Implementation Order

Follow this sequence to build the system layer by layer, each phase building on the previous one:

```
Phase 0  →  Environment, dependencies, .env, config/settings.py
Phase 1  →  Core data models (database/models.py, api/schemas/)
Phase 2  →  Sample data (tickets, policies, history, eval cases)
Phase 3  →  RAG pipeline (load → chunk → embed → store → retrieve)
Phase 4  →  Memory layer (short-term state, long-term PostgreSQL, semantic ChromaDB)
Phase 5  →  Agent tools (one tool at a time, test each)
Phase 6  →  LangGraph nodes (implement each node, wire state)
Phase 7  →  LangGraph graph (connect nodes, add conditional edges)
Phase 8  →  FastAPI endpoints (expose the graph via REST API)
Phase 9  →  Gradio UI (connect to FastAPI for demo)
Phase 10 →  Langfuse tracing (add observability to every LLM call and tool)
Phase 11 →  Evaluation scripts (measure accuracy, retrieval quality, latency)
Phase 12 →  Airflow DAGs (schedule ingestion, memory indexing, evaluations)
Phase 13 →  Security hardening (PII masking, prompt injection guard, auth)
Phase 14 →  Containerization (Docker Compose — all services locally)
Phase 15 →  CI/CD (GitHub Actions — lint, test, build, security scan)
Phase 16 →  Terraform + AWS deployment
Phase 17 →  Final validation against success metrics
```

---

## Success Criteria

The project is successful when:

- [ ] Tickets are processed end-to-end
- [ ] Responses are grounded in company policies
- [ ] Customer history is used correctly
- [ ] Similar historical cases are retrieved correctly
- [ ] Memory is stored and retrieved correctly
- [ ] Tickets are routed correctly
- [ ] Escalations occur appropriately
- [ ] Agent decisions are traceable
- [ ] Langfuse traces are available
- [ ] Evaluation metrics are available
- [ ] Airflow pipelines run successfully
- [ ] The application runs locally and on AWS
- [ ] The system demonstrates production-grade Agentic AI engineering practices

---

## Final Stack Summary

> **LangGraph + RAG + Memory + FastAPI + Gradio + PostgreSQL + ChromaDB + Airflow + Langfuse + Docker + Terraform + AWS ECS + CI/CD + Human-in-the-Loop**

This architecture maps directly to AI Engineer, Applied AI Engineer, GenAI Engineer, and Agentic AI roles.
