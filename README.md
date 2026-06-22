# AI Customer Support Automation Agent

[![GitHub](https://img.shields.io/badge/GitHub-Petlaz%2Fai--customer--support--agent-blue?logo=github)](https://github.com/Petlaz/ai-customer-support-agent)

A production-grade **Agentic AI Customer Support Platform** that automates customer support workflows using LangGraph, Retrieval-Augmented Generation (RAG), a three-layer memory system, Apache Airflow orchestration, and Langfuse observability.

The agent classifies incoming tickets, retrieves company policies and customer history, drafts grounded responses, routes tickets to the correct department, and escalates complex cases to human agents — all with full traceability.

---

## Key Features

- **LangGraph Agent Workflow** — Stateful, graph-based agent with conditional edges (auto-respond vs. escalate to human)
- **RAG Pipeline** — Retrieves relevant policy documents from ChromaDB to ground every response
- **Three-Layer Memory** — Short-term (LangGraph state), long-term (PostgreSQL), semantic (ChromaDB embeddings)
- **Tool Calling** — 13 typed tools: classification, policy retrieval, memory retrieval, routing, escalation, email, Jira, Slack
- **Human-in-the-Loop** — Low-confidence or high-risk tickets are escalated with full context attached
- **Langfuse Observability** — Every LLM call, tool call, token count, and cost is traced
- **Airflow Orchestration** — Scheduled DAGs for document ingestion, memory indexing, and evaluation runs
- **FastAPI REST API** — Fully typed endpoints with Pydantic schemas and auto-generated docs
- **Gradio Demo UI** — Chat interface for submitting tickets and viewing agent output
- **Docker + AWS ECS** — Containerised locally, deployed to AWS Fargate via Terraform

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | LangGraph, LangChain |
| LLM | **OpenAI GPT-4o** (primary) — `gpt-4o-mini` for dev, `gpt-4o` for production |
| API | FastAPI + Pydantic |
| Relational DB | PostgreSQL (SQLite locally) |
| Vector DB | ChromaDB |
| Observability | Langfuse |
| Orchestration | Apache Airflow |
| Frontend | Gradio |
| Containerisation | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Infrastructure | Terraform + AWS (ECS Fargate, RDS, S3, ECR, CloudWatch) |

---

## Agent Workflow

```
Receive Ticket
      ↓
Retrieve Long-Term Memory   ← customer history from PostgreSQL
      ↓
Retrieve Semantic Memory    ← similar past cases from ChromaDB
      ↓
Classify Ticket             ← Billing / Refund / Technical / etc.
      ↓
Retrieve Policy             ← relevant policy docs via RAG
      ↓
Draft Response              ← grounded on policy + memory + history
      ↓
Evaluate Confidence
      ↓
   [Branch]
   /       \
High        Low Confidence / Escalation Trigger
Confidence        ↓
   ↓         Escalate to Human Review
Route Ticket
   ↓
   └──────────┬──────────┘
              ↓
        Generate Summary → Store Memory → Log Decision → Langfuse Trace
              ↓
        Return Final Output
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- OpenAI API key — **recommended** (see [Why OpenAI?](#llm-provider) below)
- Anthropic API key — optional, supported as a drop-in fallback
- Langfuse account (or self-hosted)

### 1. Clone and set up environment

```bash
git clone https://github.com/your-org/ai-customer-support-agent.git
cd ai-customer-support-agent

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in your API keys and database URL
```

### 3. Run locally with Docker Compose

```bash
docker compose up --build
```

Services started:
- FastAPI → `http://localhost:8000`
- Gradio UI → `http://localhost:7860`
- Airflow → `http://localhost:8080`
- PostgreSQL → `localhost:5432`
- ChromaDB → `localhost:8001`

### 4. Ingest sample data

```bash
python scripts/ingest_documents.py   # loads policies into ChromaDB
python scripts/ingest_memory.py      # loads historical tickets into memory
python scripts/seed_database.py      # seeds PostgreSQL with sample customers
```

### 5. Run tests

```bash
pytest tests/ -v
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/tickets/analyze` | Run a ticket through the full agent workflow |
| `POST` | `/tickets/classify` | Classify a ticket only (no response generation) |
| `POST` | `/tickets/respond` | Generate a response for a pre-classified ticket |
| `POST` | `/tickets/route` | Determine routing for a ticket |
| `GET` | `/tickets/{ticket_id}` | Retrieve a stored ticket by ID |
| `GET` | `/customers/{customer_id}` | Retrieve customer history |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus-compatible metrics |

Full API docs available at `http://localhost:8000/docs` (Swagger UI) when running locally.

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key — **primary, recommended** | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key — optional fallback, swap via `config/settings.py` | No |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | Yes |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | Yes |
| `LANGFUSE_HOST` | Langfuse host URL | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `CHROMA_PERSIST_PATH` | Path for ChromaDB persistence | Yes |
| `CONFIDENCE_THRESHOLD` | Min confidence to auto-respond (default: `0.75`) | No |
| `AIRFLOW_HOME` | Airflow home directory | Yes (for Airflow) |
| `SECRET_KEY` | FastAPI JWT secret key | Yes |

See `.env.example` for the full list.

### LLM Provider

**We use OpenAI as the primary LLM provider for this project.** Reasons:

- The majority of LangGraph documentation and community examples are written against OpenAI
- Native JSON mode and function/tool calling are the most mature on the OpenAI SDK
- You will find more ready-to-use code and fewer debugging surprises

**Development:** use `gpt-4o-mini` — ~30× cheaper than `gpt-4o`, fast, and sufficient for all classification, routing, and drafting tasks during development.

**Production / evaluation:** switch to `gpt-4o` for best accuracy.

**Anthropic (Claude 3.5 Sonnet)** is fully supported as a drop-in fallback. Change one setting in `config/settings.py` and set `ANTHROPIC_API_KEY`. Useful if OpenAI has an outage or you want to compare outputs.

> Neither provider charges you until you manually add credits to your account. Set a monthly spend limit in your [OpenAI dashboard](https://platform.openai.com/settings/organization/limits) to avoid surprises.

---

## Project Structure

```
ai-customer-support-agent/
├── README.md
├── .gitignore
├── .env.example
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── airflow.Dockerfile
├── docker-compose.yml
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── dependencies.py
│   └── lifecycle.py
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── constants.py
│
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── tickets.py
│   │   ├── customers.py
│   │   ├── health.py
│   │   └── metrics.py
│   │
│   └── schemas/
│       ├── __init__.py
│       ├── ticket_schema.py
│       ├── response_schema.py
│       ├── routing_schema.py
│       ├── escalation_schema.py
│       ├── memory_schema.py
│       └── evaluation_schema.py
│
├── agents/
│   ├── __init__.py
│   ├── graph.py
│   ├── state.py
│   ├── prompts.py
│   ├── confidence.py
│   │
│   └── nodes/
│       ├── __init__.py
│       ├── receive_ticket.py
│       ├── retrieve_long_term_memory.py
│       ├── retrieve_semantic_memory.py
│       ├── classify_ticket.py
│       ├── retrieve_policy.py
│       ├── draft_response.py
│       ├── check_confidence.py
│       ├── route_ticket.py
│       ├── escalate_ticket.py
│       ├── summarize_ticket.py
│       ├── store_memory.py
│       └── log_decision.py
│
├── memory/
│   ├── __init__.py
│   ├── memory_manager.py
│   ├── short_term_memory.py
│   ├── long_term_memory.py
│   ├── semantic_memory.py
│   ├── conversation_history.py
│   ├── customer_history.py
│   ├── ticket_memory.py
│   └── memory_retriever.py
│
├── tools/
│   ├── __init__.py
│   ├── classify_ticket_tool.py
│   ├── retrieve_policy_tool.py
│   ├── retrieve_memory_tool.py
│   ├── retrieve_similar_cases_tool.py
│   ├── draft_response_tool.py
│   ├── route_ticket_tool.py
│   ├── summarize_ticket_tool.py
│   ├── escalate_to_human_tool.py
│   ├── log_decision_tool.py
│   ├── send_email_tool.py
│   ├── create_jira_ticket_tool.py
│   ├── slack_notification_tool.py
│   └── zendesk_mock_tool.py
│
├── rag/
│   ├── __init__.py
│   ├── document_loader.py
│   ├── text_extractor.py
│   ├── chunker.py
│   ├── embeddings.py
│   ├── vector_store.py
│   ├── retriever.py
│   ├── metadata_filter.py
│   └── context_formatter.py
│
├── orchestration/
│   ├── __init__.py
│   └── airflow/
│       ├── dags/
│       │   ├── document_ingestion_dag.py
│       │   ├── memory_indexing_dag.py
│       │   ├── evaluation_dag.py
│       │   └── cleanup_dag.py
│       ├── plugins/
│       │   └── .gitkeep
│       └── requirements-airflow.txt
│
├── observability/
│   ├── __init__.py
│   ├── langfuse_client.py
│   ├── trace_manager.py
│   ├── prompt_registry.py
│   ├── eval_tracker.py
│   └── cost_tracker.py
│
├── database/
│   ├── __init__.py
│   ├── db.py
│   ├── models.py
│   ├── crud.py
│   ├── session.py
│   │
│   └── migrations/
│       └── .gitkeep
│
├── security/
│   ├── __init__.py
│   ├── auth.py
│   ├── input_validation.py
│   ├── pii_masking.py
│   ├── prompt_guard.py
│   └── rate_limiter.py
│
├── monitoring/
│   ├── __init__.py
│   ├── logger.py
│   ├── metrics.py
│   ├── cloudwatch.py
│   └── dashboard_config.py
│
├── frontend/
│   ├── __init__.py
│   └── gradio_app.py
│
├── data/
│   ├── tickets/
│   │   └── sample_tickets.json
│   │
│   ├── policies/
│   │   ├── refund_policy.md
│   │   ├── billing_policy.md
│   │   ├── support_faq.md
│   │   └── technical_support_guide.md
│   │
│   ├── history/
│   │   ├── customer_history.json
│   │   ├── historical_tickets.json
│   │   └── historical_resolutions.json
│   │
│   ├── airflow_dags/
│   │   └── sample_ingestion_schedule.json
│   │
│   └── evaluation/
│       └── eval_cases.json
│
├── evaluation/
│   ├── __init__.py
│   ├── eval_classification.py
│   ├── eval_rag.py
│   ├── eval_memory.py
│   ├── eval_agent.py
│   ├── eval_latency.py
│   ├── eval_cost.py
│   └── eval_langfuse.py
│
├── tests/
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_agent_graph.py
│   ├── test_classification.py
│   ├── test_retrieval.py
│   ├── test_memory.py
│   ├── test_langfuse.py
│   ├── test_airflow_dags.py
│   ├── test_routing.py
│   ├── test_escalation.py
│   ├── test_security.py
│   └── test_evaluation.py
│
├── scripts/
│   ├── ingest_documents.py
│   ├── ingest_memory.py
│   ├── run_evaluation.py
│   ├── run_langfuse_eval.py
│   ├── seed_database.py
│   ├── start_airflow.sh
│   ├── run_local.sh
│   └── deploy_local.sh
│
├── infra/
│   └── terraform/
│       ├── main.tf
│       ├── provider.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── vpc.tf
│       ├── ecr.tf
│       ├── ecs.tf
│       ├── rds.tf
│       ├── s3.tf
│       ├── secrets.tf
│       ├── cloudwatch.tf
│       ├── airflow.tf
│       ├── langfuse.tf
│       └── iam.tf
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
├── docs/
│   ├── project_problem_definition.md
│   ├── project_checklist.md
│   ├── api_keys_setup.md
│   ├── architecture.md
│   ├── memory_architecture.md
│   ├── rag_architecture.md
│   ├── airflow_orchestration.md
│   ├── langfuse_observability.md
│   ├── api_docs.md
│   ├── deployment_guide.md
│   ├── evaluation_plan.md
│   ├── security_notes.md
│   └── future_improvements.md
│
├── notebooks/
│   ├── rag_experiments.ipynb
│   ├── memory_experiments.ipynb
│   └── evaluation_experiments.ipynb
│
└── logs/
    └── .gitkeep
```

---

## Module Overview

| Module | Description |
|--------|-------------|
| `docs/project_problem_definition.md` | Full Project Requirements Specification (PRS) — problem, objectives, architecture, tech stack |
| `docs/project_checklist.md` | End-to-end implementation checklist tracking progress across all 21 phases |
| `app/` | FastAPI application entry point, dependencies, and lifecycle hooks |
| `config/` | Settings management (Pydantic BaseSettings) and project-wide constants |
| `api/` | API route handlers and Pydantic request/response schemas |
| `agents/` | LangGraph agent graph, AgentState definition, prompts, and all graph nodes |
| `memory/` | Short-term (state), long-term (PostgreSQL), and semantic (ChromaDB) memory |
| `tools/` | Typed LangChain tools for classification, retrieval, routing, and third-party integrations |
| `rag/` | Document loading, chunking, embedding, vector store, and retrieval pipeline |
| `orchestration/` | Apache Airflow DAGs for document ingestion, memory indexing, evaluation, and cleanup |
| `observability/` | Langfuse tracing, prompt registry, evaluation tracking, and cost tracking |
| `database/` | SQLAlchemy models, CRUD operations, session management, and migrations |
| `security/` | Authentication, input validation, PII masking, prompt injection guard, rate limiting |
| `monitoring/` | Structured logging, metrics collection, CloudWatch integration, and dashboards |
| `frontend/` | Gradio chat UI for local testing and demos |
| `data/` | Sample tickets, policy documents, customer history, and evaluation cases |
| `evaluation/` | Evaluation scripts for classification, RAG, memory, agent quality, latency, and cost |
| `tests/` | Unit and integration tests for all major components |
| `scripts/` | Helper scripts for data ingestion, database seeding, evaluation, and local deployment |
| `infra/terraform/` | Terraform IaC for AWS (VPC, ECS, RDS, S3, ECR, Secrets Manager, CloudWatch) |
| `.github/workflows/` | CI/CD pipelines for linting, testing, security scanning, and deployment |
| `docs/` | Architecture diagrams, API reference, deployment guide, and evaluation plan |
| `notebooks/` | Jupyter notebooks for RAG, memory, and evaluation experiments |
| `logs/` | Runtime log output directory |

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/api_keys_setup.md](docs/api_keys_setup.md) | Step-by-step guide for creating OpenAI, Anthropic, and Langfuse API keys |
| [docs/project_problem_definition.md](docs/project_problem_definition.md) | Full Project Requirements Specification — problem, objectives, data models, walkthrough |
| [docs/project_checklist.md](docs/project_checklist.md) | End-to-end implementation checklist across 21 phases |
| [docs/architecture.md](docs/architecture.md) | System architecture diagram |
| [docs/memory_architecture.md](docs/memory_architecture.md) | Three-layer memory design |
| [docs/rag_architecture.md](docs/rag_architecture.md) | RAG pipeline design |
| [docs/airflow_orchestration.md](docs/airflow_orchestration.md) | Airflow DAG overview |
| [docs/langfuse_observability.md](docs/langfuse_observability.md) | Langfuse integration guide |
| [docs/api_docs.md](docs/api_docs.md) | REST API reference |
| [docs/deployment_guide.md](docs/deployment_guide.md) | Local and AWS deployment steps |
| [docs/evaluation_plan.md](docs/evaluation_plan.md) | Evaluation methodology and metrics |
| [docs/security_notes.md](docs/security_notes.md) | Security decisions and controls |

---

## Success Metrics (v1 Targets)

| Metric | Target |
|--------|--------|
| Classification Accuracy | ≥ 90% |
| Routing Accuracy | ≥ 90% |
| Policy Retrieval Relevance | ≥ 85% |
| Memory Retrieval Relevance | ≥ 85% |
| Hallucination Rate | ≤ 5% |
| Average Response Latency | < 5 seconds |
| Escalation Precision | ≥ 80% |
| API Availability | ≥ 99% |

---

## Out of Scope (v1)

The following are explicitly **not** implemented in version 1:

- Voice agents or phone call integration
- Multi-agent systems
- Fine-tuning or custom model training
- Knowledge graphs
- Multi-language support
- Social media integrations

---

*Built to demonstrate production-grade Agentic AI engineering — LangGraph + RAG + Memory + FastAPI + Airflow + Langfuse + Docker + Terraform + AWS.*
