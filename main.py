"""FastAPI application entry point.

Start the server:
    uvicorn main:app --reload --port 8000

Docs available at:
    http://localhost:8000/docs      (Swagger UI)
    http://localhost:8000/redoc     (ReDoc)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import customers, health, metrics, tickets

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Compile the LangGraph agent once at startup and cache it on app.state."""
    logger.info("Compiling agent graph …")
    from agents.graph import build_graph  # noqa: PLC0415
    app.state.graph = build_graph()
    logger.info("Agent graph ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="AI Customer Support Agent API",
    description=(
        "LangGraph-powered ticket triage: classify, draft, route, and escalate. "
        "Traced via Langfuse."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
app.include_router(customers.router, prefix="/customers", tags=["customers"])
