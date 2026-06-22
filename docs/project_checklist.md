# AI Customer Support Automation Agent
## End-to-End Project Checklist

Use this checklist to track implementation progress across all project phases.

> **Recommended Build Order:** Phase 0 → 1 → 2 → Core Data Models → RAG → Memory → Tools → Agent Nodes → Agent Graph → API → UI → Observability → Evaluation → Airflow → Security → Docker → CI/CD → Terraform → AWS
> Each phase builds on the previous one. Do not skip ahead — the agent graph depends on working tools, tools depend on a working RAG + memory layer.

---

## Phase 0 — Environment & Dependencies

> **Goal:** Get a working Python environment with all dependencies installed and all secrets configured before writing any application code.

- [x] Create and activate a Python virtual environment (`python -m venv .venv`)
- [x] Populate `requirements.txt` with all project dependencies
- [x] Populate `pyproject.toml` with project metadata and tool config (Ruff, MyPy, Pytest)
- [x] Copy `.env.example` → `.env` and fill in all required values:
  - [x] `OPENAI_API_KEY` — key set ✓ (add billing credits at platform.openai.com/settings/billing)
  - [x] `ANTHROPIC_API_KEY` — key set ✓ (add billing credits at console.anthropic.com/settings/billing when ready)
  - [x] `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` — set and verified ✓
  - [x] `DATABASE_URL` — set to SQLite default ✓
  - [x] `CHROMA_PERSIST_PATH` — set to `./data/chroma_db` ✓
  - [x] `AIRFLOW_HOME` — set to `./orchestration/airflow` ✓
  - [x] `SECRET_KEY` — auto-generated (64-char hex) ✓

  > See [`docs/api_keys_guide.md`](api_keys_guide.md) for step-by-step key creation instructions.
- [x] Populate `config/settings.py` with Pydantic `BaseSettings` to load `.env` values
- [x] Populate `config/constants.py` with ticket categories, department names, confidence thresholds
- [x] Verify imports work: `python -c "from config.settings import settings"`

---

## Phase 1 — Project Setup

> **Goal:** Scaffold the complete project folder structure and root configuration files. This is already done — all folders and placeholder files have been created.

### Create Project Folders

- [x] `app/`
- [x] `agents/`
- [x] `api/`
- [x] `tools/`
- [x] `rag/`
- [x] `memory/`
- [x] `database/`
- [x] `frontend/`
- [x] `data/`
- [x] `evaluation/`
- [x] `tests/`
- [x] `infra/`
- [x] `docs/`
- [x] `notebooks/`
- [x] `monitoring/`
- [x] `security/`
- [x] `orchestration/`
- [x] `observability/`

### Create Root Files

- [x] `README.md`
- [x] `.gitignore`
- [x] `.env.example`
- [x] `requirements.txt`
- [x] `Dockerfile`
- [x] `docker-compose.yml`
- [x] `airflow.Dockerfile`
- [x] `pyproject.toml`

---

## Phase 2 — Define the Use Case

> **Goal:** Fully document what the agent does, why it exists, and what success looks like. Captured in `project_problem_definition.md`. Use this as the reference document throughout the entire build.

- [x] Define what the agent does:
  - [x] Classifies customer tickets
  - [x] Retrieves company policy information
  - [x] Retrieves relevant customer history
  - [x] Retrieves similar historical tickets
  - [x] Drafts customer responses
  - [x] Routes tickets to the right department
  - [x] Escalates low-confidence cases to humans
  - [x] Logs every decision
  - [x] Learns from previous interactions
  - [x] Tracks all agent actions and LLM calls

---

## Phase 3 — Design Agent Memory

> **Goal:** Understand the three-layer memory architecture before implementing it. No code in this phase — design decisions only. The actual code is written in Phase 6.

### Short-Term Memory

- [ ] Implement using **LangGraph State**
- [ ] Store conversation history
- [ ] Store current workflow state
- [ ] Store previous agent actions
- [ ] Store tool outputs

### Long-Term Memory

- [ ] Implement using **PostgreSQL**
- [ ] Store customer profiles
- [ ] Store historical tickets
- [ ] Store historical resolutions
- [ ] Store escalation history
- [ ] Store customer preferences

### Semantic Memory

- [ ] Implement using **Chroma Vector Database**
- [ ] Store ticket embeddings
- [ ] Store resolution embeddings
- [ ] Store conversation embeddings
- [ ] Retrieve similar tickets
- [ ] Retrieve similar resolutions
- [ ] Retrieve similar customer issues

---

## Phase 4 — Create Sample Data

> **Goal:** Populate realistic sample data before building any retrieval or agent logic. The agent and RAG pipeline need real data to test against from day one.

- [x] `data/tickets/sample_tickets.json` — file created
- [x] `data/policies/refund_policy.md` — file created
- [x] `data/policies/billing_policy.md` — file created
- [x] `data/policies/support_faq.md` — file created
- [x] `data/history/customer_history.json` — file created
- [x] `data/history/historical_resolutions.json` — file created
- [x] `data/evaluation/eval_cases.json` — file created
- [ ] Add realistic content to `sample_tickets.json` (10–20 varied tickets across all categories)
- [ ] Add realistic content to `refund_policy.md` (company refund rules)
- [ ] Add realistic content to `billing_policy.md` (billing cycles, charges, disputes)
- [ ] Add realistic content to `support_faq.md` (common questions + answers)
- [ ] Add realistic content to `customer_history.json` (2–3 customers with prior tickets)
- [ ] Add realistic content to `historical_resolutions.json` (past tickets + resolutions)
- [ ] Add realistic content to `eval_cases.json` (input/expected-output pairs for evaluation)

---

## Phase 5 — Build the RAG Layer

> **Goal:** Build the pipeline that loads company policy documents, chunks them, generates embeddings, stores them in ChromaDB, and retrieves relevant chunks at query time. This layer powers the `retrieve_policy` agent node and the `retrieve_similar_cases` tool.
> 
> **Test:** After this phase, you should be able to query ChromaDB with a ticket message and get back relevant policy chunks.

### Core Components

- [x] `rag/document_loader.py` — Document loading
- [x] `rag/text_extractor.py` — Text extraction
- [x] `rag/chunker.py` — Text chunking
- [x] `rag/embeddings.py` — Embedding generation
- [x] `rag/vector_store.py` — Vector storage (ChromaDB)
- [x] `rag/retriever.py` — Semantic retrieval
- [x] `rag/metadata_filter.py` — Metadata filtering
- [x] `rag/context_formatter.py` — Context formatting

### Airflow Integration

- [x] `orchestration/airflow/dags/document_ingestion_dag.py` — Policy ingestion DAG file created
- [ ] Knowledge base refresh DAG (implement)
- [ ] Embedding generation DAG (implement)
- [ ] Vector store synchronization DAG (implement)

---

## Phase 6 — Build the Memory Layer

> **Goal:** Implement all three memory types. Short-term memory lives in LangGraph state (no extra code needed beyond `agents/state.py`). Long-term memory reads/writes customer history from PostgreSQL. Semantic memory reads/writes ticket embeddings from ChromaDB.
>
> **Test:** After this phase, you should be able to query a customer's ticket history and retrieve similar historical cases by embedding similarity.

### Components

- [x] `memory/memory_manager.py`
- [x] `memory/short_term_memory.py`
- [x] `memory/long_term_memory.py`
- [x] `memory/semantic_memory.py`
- [x] `memory/conversation_history.py`
- [x] `memory/customer_history.py`
- [x] `memory/ticket_memory.py`
- [x] `memory/memory_retriever.py`

### Airflow Integration

- [x] `orchestration/airflow/dags/memory_indexing_dag.py` — Memory indexing DAG file created
- [ ] Embedding refresh DAG (implement)
- [ ] Historical ticket ingestion DAG (implement)

---

## Phase 7 — Build the LangGraph Agent Workflow

> **Goal:** Implement every graph node and wire them together into a stateful LangGraph graph with conditional edges. Each node receives `AgentState`, does one job, and returns an updated state. The `check_confidence` node determines whether the graph routes to `route_ticket` or `escalate_ticket`.
>
> **Test:** After this phase, you should be able to invoke the graph with a `TicketInput` and receive a complete `AgentState` with all fields populated.

### Agent Graph Nodes

- [x] `agents/nodes/receive_ticket.py`
- [x] `agents/nodes/retrieve_long_term_memory.py`
- [x] `agents/nodes/retrieve_semantic_memory.py`
- [x] `agents/nodes/classify_ticket.py`
- [x] `agents/nodes/retrieve_policy.py`
- [x] `agents/nodes/draft_response.py`
- [x] `agents/nodes/check_confidence.py`
- [x] `agents/nodes/route_ticket.py`
- [x] `agents/nodes/escalate_ticket.py`
- [x] `agents/nodes/summarize_ticket.py`
- [x] `agents/nodes/store_memory.py`
- [x] `agents/nodes/log_decision.py`

### Agent Core Files

- [x] `agents/graph.py` — LangGraph workflow definition
- [x] `agents/state.py` — LangGraph state schema
- [x] `agents/prompts.py` — Prompt templates
- [x] `agents/confidence.py` — Confidence scoring logic

### Langfuse Integration

- [ ] Trace workflow execution
- [ ] Trace tool calls
- [ ] Trace prompts
- [ ] Trace retrieved documents
- [ ] Trace retrieved memories
- [ ] Trace agent decisions
- [ ] Track token usage
- [ ] Track latency
- [ ] Track cost

---

## Phase 8 — Define Agent Tools

> **Goal:** Implement each LangChain/LangGraph tool as a callable function with typed input/output schemas. Tools are the primitive operations the agent nodes call — each tool does exactly one thing and is independently testable.

- [x] `tools/classify_ticket_tool.py`
- [x] `tools/retrieve_policy_tool.py`
- [x] `tools/retrieve_memory_tool.py`
- [x] `tools/retrieve_similar_cases_tool.py`
- [x] `tools/draft_response_tool.py`
- [x] `tools/route_ticket_tool.py`
- [x] `tools/summarize_ticket_tool.py`
- [x] `tools/escalate_to_human_tool.py`
- [x] `tools/log_decision_tool.py`
- [x] `tools/send_email_tool.py`
- [x] `tools/create_jira_ticket_tool.py`
- [x] `tools/slack_notification_tool.py`
- [x] `tools/zendesk_mock_tool.py`

Each tool must include:

- [ ] Input schema (Pydantic)
- [ ] Output schema (Pydantic)
- [ ] Error handling
- [ ] Logging
- [ ] Unit tests

---

## Phase 9 — Human-in-the-Loop

> **Goal:** Implement the escalation pathway. When `check_confidence` determines the agent should not auto-respond, the `escalate_ticket` node packages all available context and flags the ticket for human review. The human reviewer receives everything they need to make a decision without re-reading the original thread.

### Escalation Triggers

- [ ] Low confidence score
- [ ] Missing policy information
- [ ] Legal concern detected
- [ ] Compliance issue detected
- [ ] High-value refund request
- [ ] Sensitive customer data detected
- [ ] Ambiguous / unclear request

### Escalation Payload

- [ ] Customer history
- [ ] Similar tickets
- [ ] Retrieved policies
- [ ] Draft response
- [ ] Confidence score

---

## Phase 10 — Build FastAPI Backend

> **Goal:** Expose the LangGraph agent as a REST API. The `POST /tickets/analyze` endpoint is the primary integration point — it receives a ticket, runs the full agent graph, and returns a structured response. All other endpoints support ticket management and monitoring.

### Endpoints

- [ ] `POST /tickets/analyze`
- [ ] `POST /tickets/classify`
- [ ] `POST /tickets/respond`
- [ ] `POST /tickets/route`
- [ ] `POST /tickets/history`
- [ ] `GET /tickets/{ticket_id}`
- [ ] `GET /customers/{customer_id}`
- [ ] `GET /health`
- [ ] `GET /metrics`

### API Files

- [x] `api/routes/tickets.py`
- [x] `api/routes/customers.py`
- [x] `api/routes/health.py`
- [x] `api/routes/metrics.py`
- [x] `api/schemas/ticket_schema.py`
- [x] `api/schemas/response_schema.py`
- [x] `api/schemas/routing_schema.py`
- [x] `api/schemas/escalation_schema.py`
- [x] `api/schemas/memory_schema.py`
- [x] `api/schemas/evaluation_schema.py`

---

## Phase 11 — Database Layer

> **Goal:** Implement SQLAlchemy models and CRUD operations for persisting tickets, customers, responses, routing decisions, and escalations. Use SQLite locally (zero config) and PostgreSQL in production (Amazon RDS).

### Local Development

- [ ] SQLite for local development

### Production

- [ ] PostgreSQL on Amazon RDS

### Database Files

- [x] `database/models.py` — SQLAlchemy models
- [x] `database/crud.py` — CRUD operations
- [x] `database/db.py` — Database connection
- [x] `database/session.py` — Session management

### Tables to Store

- [ ] Customers
- [ ] Tickets
- [ ] Conversations
- [ ] Responses
- [ ] Routing decisions
- [ ] Escalations
- [ ] Agent logs
- [ ] Evaluation results

---

## Phase 12 — Build UI (Gradio)

> **Goal:** Build a simple chat-style interface in Gradio that lets you submit tickets and see the full agent output — classification, response, routing, escalation status, confidence score, and a link to the Langfuse trace. Used for demos and manual testing.

- [x] `frontend/gradio_app.py`

### UI Features

- [ ] Submit ticket form
- [ ] View agent workflow output
- [ ] View retrieved policies
- [ ] View retrieved memories
- [ ] View similar tickets
- [ ] View routing decision
- [ ] View escalation decision
- [ ] View Langfuse trace link
- [ ] View confidence score

---

## Phase 13 — Add Evaluation

> **Goal:** Measure the system against the success metrics defined in the PRS. Run each eval script against the `data/evaluation/eval_cases.json` dataset. Track results in Langfuse. Use Airflow to schedule nightly evaluation runs.

### Evaluation Scripts

- [x] `evaluation/eval_classification.py` — Classification accuracy
- [x] `evaluation/eval_rag.py` — Retrieval relevance
- [x] `evaluation/eval_memory.py` — Memory accuracy
- [x] `evaluation/eval_agent.py` — End-to-end agent quality
- [x] `evaluation/eval_latency.py` — Latency benchmarks
- [x] `evaluation/eval_cost.py` — Cost tracking
- [x] `evaluation/eval_langfuse.py` — Langfuse evaluation integration

### Langfuse Evaluation

- [ ] Track prompt quality
- [ ] Track tool performance
- [ ] Track retrieval quality
- [ ] Track agent quality
- [ ] Track cost trends
- [ ] Track token usage
- [ ] Track latency

### Airflow Evaluation

- [x] `orchestration/airflow/dags/evaluation_dag.py` — Evaluation DAG file created
- [ ] Weekly benchmark runs (implement)
- [ ] Regression testing (implement)

---

## Phase 14 — Reliability Features

> **Goal:** Make the system production-safe. LLM calls can fail, time out, or return malformed output. Every external call needs retry logic, timeouts, and a graceful fallback so one bad LLM response doesn’t crash the entire workflow.

- [ ] Retries on LLM calls
- [ ] Timeouts on tool calls
- [ ] Circuit breakers
- [ ] Structured logging with request IDs
- [ ] Input validation
- [ ] Safe response rules
- [ ] Fallback responses

---

## Phase 15 — Security

> **Goal:** Harden the system against the OWASP Top 10 and LLM-specific risks. PII must be masked before being sent to external LLM APIs. User inputs must be sanitized to prevent prompt injection. All credentials must come from environment variables or AWS Secrets Manager — never hardcoded.

- [x] `security/auth.py` — Authentication and authorization
- [x] `security/input_validation.py` — Input sanitization
- [x] `security/pii_masking.py` — PII masking before LLM calls
- [x] `security/prompt_guard.py` — Prompt injection protection
- [x] `security/rate_limiter.py` — Rate limiting
- [ ] AWS Secrets Manager integration for credentials
- [ ] Audit logging for all sensitive operations

---

## Phase 16 — Containerization

> **Goal:** Run the entire stack locally with a single `docker compose up` command. This validates that all services integrate correctly before deploying to AWS.

### Local Docker Services

- [ ] FastAPI service
- [ ] PostgreSQL service
- [ ] ChromaDB service
- [ ] Gradio service
- [ ] Airflow service (webserver + scheduler + worker)
- [ ] Langfuse service (optional local)

### Docker Files

- [x] `Dockerfile` — FastAPI app
- [x] `airflow.Dockerfile` — Airflow service
- [x] `docker-compose.yml` — All local services

---

## Phase 17 — CI/CD

> **Goal:** Automate testing, linting, security scanning, and deployment on every push to `main`. The CI pipeline catches regressions before they reach production. The deploy pipeline pushes new Docker images to ECR and updates the ECS service.

### GitHub Actions Workflows

- [x] `.github/workflows/ci.yml` — File created
  - [ ] Ruff linting (configure)
  - [ ] MyPy type checking (configure)
  - [ ] Pytest unit tests (configure)
  - [ ] Integration tests (configure)
  - [ ] Docker build validation (configure)
  - [ ] Security scan (Trivy / Bandit) (configure)
  - [ ] Terraform validate (configure)

- [x] `.github/workflows/deploy.yml` — File created
  - [ ] Deploy to AWS ECS (configure)
  - [ ] Migrate database (configure)
  - [ ] Smoke tests post-deploy (configure)

---

## Phase 18 — AWS Deployment

> **Goal:** Deploy the production system to AWS. FastAPI and Gradio run on ECS Fargate. PostgreSQL runs on RDS. S3 stores policy documents and embeddings. Airflow runs on ECS (or MWAA). All infrastructure is provisioned by Terraform.

| Component | Service | Status |
|-----------|---------|--------|
| Frontend (Gradio) | ECS Fargate | Not deployed |
| Backend (FastAPI) | ECS Fargate | Not deployed |
| Relational Database | Amazon RDS PostgreSQL | Not deployed |
| Vector Store | ChromaDB on ECS | Not deployed |
| Storage | Amazon S3 | Not deployed |
| Orchestration | Airflow on ECS or Amazon MWAA | Not deployed |
| Observability | Langfuse + CloudWatch | Not deployed |
| Infrastructure | Terraform | Not provisioned |

### Deployment Steps

- [ ] Configure AWS CLI credentials and target region
- [ ] Create S3 bucket for Terraform state (`terraform init`)
- [ ] Run `terraform plan` — review all resources to be created
- [ ] Run `terraform apply` — provision VPC, ECR, ECS, RDS, S3, IAM, Secrets Manager
- [ ] Build and push Docker images to ECR (`docker build` + `docker push`)
- [ ] Run database migrations on RDS (`alembic upgrade head` or `scripts/seed_database.py`)
- [ ] Ingest policy documents to S3 + ChromaDB (`scripts/ingest_documents.py`)
- [ ] Ingest historical memory to PostgreSQL + ChromaDB (`scripts/ingest_memory.py`)
- [ ] Verify FastAPI health endpoint: `GET /health` returns `200 OK`
- [ ] Verify Gradio UI loads and can submit a ticket
- [ ] Verify Langfuse traces appear for submitted tickets
- [ ] Verify Airflow DAGs are visible and can be triggered
- [ ] Verify CloudWatch logs and metrics are flowing
- [ ] Run smoke tests against production endpoint

### Optional AWS Services

- [ ] AWS Bedrock (alternative LLM provider)
- [ ] Amazon OpenSearch (alternative vector store)
- [ ] AWS Lambda (event-driven processing)
- [ ] Amazon SQS (message queuing)
- [ ] Amazon SNS (notifications)

---

## Phase 19 — Terraform Infrastructure

> **Goal:** Define all AWS infrastructure as code. Every resource — VPC, ECS clusters, RDS instance, S3 buckets, IAM roles, Secrets Manager entries — must be reproducible from a single `terraform apply`. No manual console clicks.

### Required Resources

- [x] `infra/terraform/vpc.tf` — VPC and subnets
- [x] `infra/terraform/ecr.tf` — ECR container registry
- [x] `infra/terraform/ecs.tf` — ECS clusters and services
- [x] `infra/terraform/rds.tf` — RDS PostgreSQL instance
- [x] `infra/terraform/s3.tf` — S3 buckets
- [x] `infra/terraform/secrets.tf` — Secrets Manager
- [x] `infra/terraform/cloudwatch.tf` — CloudWatch logs and alarms
- [x] `infra/terraform/iam.tf` — IAM roles and policies
- [x] `infra/terraform/airflow.tf` — Airflow infrastructure
- [x] `infra/terraform/langfuse.tf` — Langfuse infrastructure
- [x] `infra/terraform/main.tf` — Root module
- [x] `infra/terraform/provider.tf` — AWS provider config
- [x] `infra/terraform/variables.tf` — Input variables
- [x] `infra/terraform/outputs.tf` — Output values

### Optional

- [ ] Amazon OpenSearch
- [ ] Amazon MWAA

---

## Phase 20 — Monitoring & Observability

> **Goal:** Know when the system is failing before users do. CloudWatch tracks infrastructure health (latency, error rates, API availability). Langfuse tracks AI health (prompt quality, token usage, cost trends, evaluation scores). Structured logs connect the two.

### What to Monitor

- [ ] API uptime
- [ ] LLM call failures
- [ ] Tool call failures
- [ ] Retrieval failures
- [ ] Memory failures
- [ ] Escalation rate
- [ ] Response latency
- [ ] Token usage
- [ ] Cost per request
- [ ] Error rate

### Monitoring Components

- [x] `monitoring/logger.py` — Structured JSON logging
- [x] `monitoring/metrics.py` — Metrics collection
- [x] `monitoring/cloudwatch.py` — CloudWatch integration
- [x] `monitoring/dashboard_config.py` — Dashboard configuration

### Observability Tools

- [ ] CloudWatch Logs
- [ ] CloudWatch Metrics and Alarms
- [ ] Langfuse Tracing
- [ ] Langfuse Evaluations
- [ ] Langfuse Prompt Management
- [ ] Structured JSON Logging
- [ ] Dashboards

---

## Phase 21 — Documentation

> **Goal:** Write documentation good enough that a new engineer can understand the system, run it locally, and deploy it to AWS without asking for help. Every architectural decision should be explained, not just described.

### Docs Folder

- [x] `docs/project_problem_definition.md` — Full PRS (problem, objectives, architecture, data models)
- [x] `docs/architecture.md` — Architecture diagram placeholder
- [x] `docs/memory_architecture.md` — Memory architecture placeholder
- [x] `docs/rag_architecture.md` — RAG pipeline placeholder
- [x] `docs/airflow_orchestration.md` — Airflow DAG overview placeholder
- [x] `docs/langfuse_observability.md` — Langfuse integration guide placeholder
- [x] `docs/api_docs.md` — REST API reference placeholder
- [x] `docs/deployment_guide.md` — Deployment guide placeholder
- [x] `docs/evaluation_plan.md` — Evaluation methodology placeholder
- [x] `docs/security_notes.md` — Security notes placeholder
- [x] `docs/future_improvements.md` — Future improvements placeholder

### README

The `README.md` must explain:

- [ ] Why LangGraph was chosen
- [ ] How RAG works in this system
- [ ] How Memory works (short-term, long-term, semantic)
- [ ] How Airflow orchestrates ingestion and evaluations
- [ ] How Langfuse traces and evaluates the agent
- [ ] How Human Escalation works
- [ ] How the system is deployed
- [ ] How the system is evaluated

---

## Final Validation Checklist

- [ ] Tickets are processed end-to-end
- [ ] Responses are grounded in company policies
- [ ] Customer history is used correctly
- [ ] Similar historical cases are retrieved correctly
- [ ] Memory is stored and retrieved correctly
- [ ] Tickets are routed correctly
- [ ] Escalations occur appropriately
- [ ] Agent decisions are traceable in Langfuse
- [ ] Langfuse traces and evaluations are available
- [ ] Evaluation metrics meet defined success targets
- [ ] Airflow pipelines run successfully
- [ ] Application runs locally via Docker Compose
- [ ] Application deploys successfully to AWS
- [ ] CI/CD pipeline passes all checks
- [ ] System demonstrates production-grade Agentic AI engineering

---

## Success Metrics Reference

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
