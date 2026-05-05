"""
=============================================================================
Apexon AI Agent — Database Connection Core Service
=============================================================================
Manages the asynchronous PostgreSQL connection pool and the LangGraph
checkpoint saver. Both are initialized during the FastAPI application
lifespan and torn down cleanly on shutdown.

Architecture:
    ┌─────────────────────┐
    │   FastAPI Lifespan   │
    │                     │
    │  ┌───────────────┐  │
    │  │ AsyncConnPool  │──►  psycopg_pool.AsyncConnectionPool
    │  └───────────────┘  │
    │  ┌───────────────┐  │
    │  │ PostgresSaver  │──►  langgraph-checkpoint-postgres
    │  └───────────────┘  │
    └─────────────────────┘

The pool and checkpoint saver are attached to `app.state` so that any
request handler can access them without global mutable state.

Usage:
    This module is consumed by mainAppService.py — not imported directly
    by route handlers. Route handlers access the pool via `request.app.state`.
=============================================================================
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from backend.core.configCoreService import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def db_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager that:
      1. Opens an async PostgreSQL connection pool on startup.
      2. Initializes the LangGraph AsyncPostgresSaver (creates checkpoint
         tables if they don't exist) using autocommit to avoid the
         CREATE INDEX CONCURRENTLY transaction block error.
      3. Attaches both to `app.state` for request-scoped access.
      4. Closes the pool cleanly on shutdown.

    Args:
        app: The FastAPI application instance.

    Yields:
        None — control returns to FastAPI to serve requests.
    """
    settings = get_settings()

    # -------------------------------------------------------------------------
    # 1. Open the async connection pool
    # -------------------------------------------------------------------------
    logger.info("Opening async PostgreSQL connection pool...")
    pool = AsyncConnectionPool(
        conninfo=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        open=False,
    )
    await pool.open()
    logger.info("PostgreSQL connection pool is ready.")

    # -------------------------------------------------------------------------
    # 2. Initialize the LangGraph checkpoint saver
    # -------------------------------------------------------------------------
    # NOTE: AsyncPostgresSaver.setup() runs DDL including
    # CREATE INDEX CONCURRENTLY, which CANNOT run inside a transaction block.
    # We use a separate autocommit connection for the setup phase, then
    # hand the pool to the saver for runtime operations.
    # -------------------------------------------------------------------------
    logger.info("Initializing LangGraph AsyncPostgresSaver...")
    async with await psycopg.AsyncConnection.connect(
        settings.DATABASE_URL, autocommit=True
    ) as setup_conn:
        checkpoint_saver = AsyncPostgresSaver(setup_conn)
        await checkpoint_saver.setup()
    logger.info("LangGraph checkpoint tables are ready.")

    # Create the runtime saver using the connection pool
    runtime_saver = AsyncPostgresSaver(pool)

    # -------------------------------------------------------------------------
    # 3. Attach to app.state for downstream access
    # -------------------------------------------------------------------------
    app.state.db_pool = pool
    app.state.checkpoint_saver = runtime_saver

    yield

    # -------------------------------------------------------------------------
    # 4. Cleanup on shutdown
    # -------------------------------------------------------------------------
    logger.info("Closing PostgreSQL connection pool...")
    await pool.close()
    logger.info("PostgreSQL connection pool closed.")
