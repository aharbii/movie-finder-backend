"""Movie Finder FastAPI application entry-point.

Run locally:
    make up
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from chain import compile_graph  # type: ignore[attr-defined]
from chain.utils.logger import get_logger
from fastapi import Depends, FastAPI, HTTPException, status

from app.config import get_config
from app.dependencies import get_store, set_graph, set_store
from app.routers import auth, chat
from app.session.store import SessionStore

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = get_config()
    logger.info("Starting Movie Finder API [env=%s port=%d]", cfg.app_env, cfg.app_port)

    # --- Session store ---
    store = SessionStore(cfg.database_url)
    await store.connect()
    set_store(store)
    logger.info("Session store ready (PostgreSQL)")

    # --- LangGraph (singleton per process) ---
    graph = compile_graph()
    set_graph(graph)
    logger.info("LangGraph compiled and ready")

    yield

    await store.close()
    logger.info("Session store closed — shutting down")


app = FastAPI(
    title="Movie Finder API",
    description="AI-powered movie discovery and Q&A via LangGraph.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(chat.router)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Backwards-compatible liveness probe."""
    return await health_live()


@app.get("/health/live", tags=["ops"])
async def health_live() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["ops"])
async def health_ready(
    store: Annotated[SessionStore, Depends(get_store)],
) -> dict[str, str]:
    """Readiness probe that verifies the database pool is available."""
    try:
        await store.ping()
    except Exception as exc:
        logger.warning("Readiness probe failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session store unavailable",
        ) from exc
    return {"status": "ok"}
