"""Movie Finder FastAPI application entry-point.

Run locally:
    make up
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_config
from app.dependencies import get_store, set_graph, set_store
from app.limiting import limiter
from app.routers import auth, chat
from app.session.store import SessionStore
from chain import checkpoint_lifespan, compile_graph
from chain.utils.logger import get_logger

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver

logger = get_logger(__name__)
cfg = get_config()


def _retry_after_value(exc: RateLimitExceeded) -> str:
    limit = getattr(exc, "limit", None)
    if limit is not None and hasattr(limit, "get_expiry"):
        return str(int(limit.get_expiry()))
    return "60"


async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a JSON 429 response with Retry-After metadata."""
    del request

    response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    if isinstance(exc, RateLimitExceeded):
        response.headers["Retry-After"] = _retry_after_value(exc)
    return response


async def _open_checkpointer(
    database_url: str,
) -> tuple[
    AbstractAsyncContextManager[BaseCheckpointSaver[Any]],
    BaseCheckpointSaver[Any],
]:
    """Create and enter the process-scoped LangGraph checkpointer context."""
    checkpointer_context = checkpoint_lifespan(database_url)
    checkpointer = await checkpointer_context.__aenter__()
    return checkpointer_context, checkpointer


async def _close_checkpointer(
    checkpointer_context: AbstractAsyncContextManager[BaseCheckpointSaver[Any]] | None,
) -> None:
    """Close the process-scoped LangGraph checkpointer context when present."""
    if checkpointer_context is not None:
        await checkpointer_context.__aexit__(None, None, None)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize application singletons for the lifetime of the process."""
    runtime_config = get_config()
    logger.info(
        "Starting Movie Finder API [env=%s port=%d]",
        runtime_config.app_env,
        runtime_config.app_port,
    )

    # --- Session store ---
    store = SessionStore(runtime_config.database_url)
    await store.connect()
    set_store(store)
    logger.info("Session store ready (PostgreSQL)")

    checkpointer_context: AbstractAsyncContextManager[BaseCheckpointSaver[Any]] | None = None

    try:
        # --- LangGraph checkpointer + graph (singleton per process) ---
        checkpointer_context, checkpointer = await _open_checkpointer(runtime_config.database_url)
        app.state.checkpointer_context = checkpointer_context
        app.state.checkpointer = checkpointer
        graph = compile_graph(checkpointer=checkpointer)
        set_graph(graph)
        logger.info("LangGraph compiled with shared checkpointer")

        yield
    finally:
        await _close_checkpointer(checkpointer_context)
        if checkpointer_context is not None:
            logger.info("LangGraph checkpointer closed")
        await store.close()
        logger.info("Session store closed — shutting down")


app = FastAPI(
    title="Movie Finder API",
    description="AI-powered movie discovery and Q&A via LangGraph.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(SlowAPIMiddleware)
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
