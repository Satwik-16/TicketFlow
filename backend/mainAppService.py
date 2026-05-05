"""
=============================================================================
Apexon AI Agent — Main Application Service
=============================================================================
FastAPI application entry point. Wires up:
    • The database lifespan (connection pool + LangGraph checkpointer).
    • CORS middleware for frontend communication.
    • API route mounting for the chat streaming endpoint.

Run locally:
    uvicorn backend.mainAppService:app --reload --host 0.0.0.0 --port 8000

Architecture:
    This is the single source of truth for the FastAPI application instance.
    All lifespans, middleware, and routers attach here.
=============================================================================
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.dbConnectionCoreService import db_lifespan
from backend.routes.chatApiRouteService import chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Apexon AI Agent — IT Helpdesk Accelerator",
    description=(
        "Enterprise-grade agentic AI IT helpdesk accelerator. "
        "Categorizes issues, creates tickets, and escalates to humans "
        "when confidence is low — all via a streaming chat interface."
    ),
    version="0.1.0",
    lifespan=db_lifespan,
)

# In production, restrict `allow_origins` to the actual frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Infrastructure"])
async def health_check() -> dict[str, str]:
    """
    Lightweight liveness probe for container orchestration (Docker, K8s).
    Returns 200 if the FastAPI process is alive.
    """
    return {"status": "healthy", "service": "apexon-ai-agent"}


app.include_router(chat_router, prefix="/api")

logger.info("Apexon AI Agent application initialized — routes mounted at /api.")

