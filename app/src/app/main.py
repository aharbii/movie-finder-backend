"""Movie Finder FastAPI application entry-point.

Run locally:
    make up
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

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
from chain import compile_graph
from chain.utils.logger import get_logger

logger = get_logger(__name__)
cfg = get_config()


def _retry_after_value(exc: RateLimitExceeded) -> str:
    limit = getattr(exc, "limit", None)
    if limit is not None and hasattr(limit, "get_expiry"):
        return str(int(limit.get_expiry()))
    return "60"


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a JSON 429 response with Retry-After metadata."""
    response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    response.headers["Retry-After"] = _retry_after_value(exc)
    return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize application singletons for the lifetime of the process."""
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
