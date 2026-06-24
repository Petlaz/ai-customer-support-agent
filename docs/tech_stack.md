# Tech Stack

Technologies used in this project with a brief explanation of each role.
Updated as the project progresses.

---

## Agent Framework

| Technology | Version | Role |
|------------|---------|------|
| LangGraph | >=0.2.0 | Stateful agent workflow — defines the graph of nodes (classify, retrieve, draft, route, escalate) with conditional edges for human-in-the-loop |
| LangChain | >=0.3.0 | Tools, document loaders, text splitters, retrievers, and prompt templates that the agent nodes use |

## LLM Providers

| Technology | Version | Role |
|------------|---------|------|
| OpenAI | >=1.40.0 | Primary LLM — `gpt-4o-mini` for development (fast, cheap), `gpt-4o` for production. Also provides `text-embedding-3-small` for all vector embeddings |
| Anthropic | >=0.31.0 | Optional fallback LLM — `claude-3-5-sonnet-20241022`. Switch via `LLM_PROVIDER=anthropic` in `.env` |

## API Layer

| Technology | Version | Role |
|------------|---------|------|
| FastAPI | >=0.115.0 | REST API — exposes the agent as HTTP endpoints. Auto-generates Swagger docs at `/docs` |
| Pydantic | >=2.7.0 | Data validation — all request/response models and agent state fields are Pydantic or TypedDict schemas |
| pydantic-settings | >=2.3.0 | Loads all configuration from `.env` into a typed `Settings` object |
| Uvicorn | >=0.30.0 | ASGI server that runs the FastAPI application |

## Databases

| Technology | Version | Role |
|------------|---------|------|
| SQLAlchemy | >=2.0.0 | ORM — maps Python classes to database tables (customers, tickets, escalations, agent logs) |
| Alembic | >=1.13.0 | Database migrations — version-controls schema changes |
| SQLite | built-in | Local development database — zero config, stored at `data/support_agent.db` |
| PostgreSQL | - | Production database — Amazon RDS. Swap by changing `DATABASE_URL` in `.env` |
| psycopg2-binary | >=2.9.0 | PostgreSQL driver for SQLAlchemy |

## Vector Store (Semantic Memory + RAG)

| Technology | Version | Role |
|------------|---------|------|
| ChromaDB | >=0.5.0 | Vector database — stores document chunk embeddings (RAG) and historical ticket embeddings (semantic memory). Runs in-process locally |

## Observability

| Technology | Version | Role |
|------------|---------|------|
| Langfuse | >=2.0.0 | LLM observability — traces every LLM call, tool call, retrieved document, token count, and cost. US region: `https://us.cloud.langfuse.com` |

## Orchestration

| Technology | Version | Role |
|------------|---------|------|
| Apache Airflow | >=2.9.0 | Scheduled pipelines — document ingestion, memory indexing, evaluation runs, and maintenance jobs |

## Frontend

| Technology | Version | Role |
|------------|---------|------|
| Gradio | >=4.40.0 | Demo UI — chat-style interface to submit tickets and view agent output without building a full frontend |

## Security

| Technology | Version | Role |
|------------|---------|------|
| python-jose | >=3.3.0 | JWT token generation and validation for API authentication |
| passlib | >=1.7.4 | Password hashing |

## Infrastructure & Deployment

| Technology | Version | Role |
|------------|---------|------|
| Docker | - | Containerises the FastAPI app, Airflow, and all services for consistent environments |
| Docker Compose | - | Runs all services locally (API, database, ChromaDB, Airflow) with a single command |
| Terraform | >=1.8.0 | Infrastructure as Code — provisions AWS resources (VPC, ECS Fargate, RDS, S3, ECR, Secrets Manager) |
| AWS ECS Fargate | - | Runs the containerised application in production — serverless container compute |
| Amazon RDS | - | Managed PostgreSQL in production |
| Amazon S3 | - | Stores policy documents and data exports |
| CloudWatch | - | AWS monitoring and log aggregation |

## CI/CD

| Technology | Version | Role |
|------------|---------|------|
| GitHub Actions | - | Automated pipeline — lint (Ruff), type check (MyPy), tests (Pytest), Docker build, security scan on every push |

## Development Tools

| Technology | Version | Role |
|------------|---------|------|
| Ruff | >=0.5.0 | Linter and formatter — enforces code style (line length 100, isort) |
| MyPy | >=1.10.0 | Static type checker |
| Pytest | >=8.2.0 | Test framework — async tests via `pytest-asyncio`, coverage via `pytest-cov` |

---

## Status

| Provider | Status |
|----------|--------|
| OpenAI | Key valid — billing credits not yet loaded (API calls fail with 429) |
| Anthropic | Key valid — billing credits not yet loaded (400 insufficient_quota) |
| Langfuse | Connected and verified (US region) |
| SQLite / SQLAlchemy | Connected — 8 tables created |
| ChromaDB | Not yet initialised (Phase 5) |
