"""Shared fixtures for the app test suite.

Design:
- SessionStore uses a real PostgreSQL database for unit tests.
  Set DATABASE_URL to point at a test database (tables are truncated
  between tests for isolation).  Default: postgresql://postgres:postgres@localhost:5432/movie_finder_test # pragma: allowlist secret
- LangGraph is fully mocked; no chain or LLM configuration is needed.
- FastAPI's lifespan is replaced with a no-op so compile_graph() is never
  called (avoids requiring QDRANT_URL / ANTHROPIC_API_KEY in tests).
- Dependencies are injected via FastAPI's dependency_overrides mechanism.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from langchain_core.messages import AIMessage

# Set required env vars before any app module is imported.
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-pytest-only-1234567890abc")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/movie_finder_test",  # pragma: allowlist secret
)


# ---------------------------------------------------------------------------
# Config isolation — clear LRU cache so each test gets a fresh AppConfig
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config_cache() -> AsyncGenerator[None]:
    from app.config import get_config

    get_config.cache_clear()
    yield  # type: ignore[misc]
    get_config.cache_clear()


# ---------------------------------------------------------------------------
# PostgreSQL session store — fresh (truncated) state per test
# ---------------------------------------------------------------------------


@pytest.fixture
async def store() -> AsyncGenerator[Any]:
    from app.session.store import SessionStore

    db_url = os.environ["DATABASE_URL"]
    s = SessionStore(db_url)
    await s.connect()

    # Truncate all tables so each test starts with an empty database.
    # CASCADE handles the FK order automatically.
    async with s._p.acquire() as conn:
        await conn.execute("TRUNCATE messages, sessions, users RESTART IDENTITY CASCADE")

    yield s
    await s.close()


# ---------------------------------------------------------------------------
# Mock LangGraph — emits one token event then a done event
# ---------------------------------------------------------------------------


def _make_mock_graph(
    phase: str = "confirmation",
    reply: str = "Here are some movies for you.",
    enriched_movies: list[dict[str, Any]] | None = None,
    confirmed_movie_data: dict[str, Any] | None = None,
    emit_tokens: bool = True,
) -> MagicMock:
    """Return a MagicMock whose astream_events is an async generator."""
    output: dict[str, Any] = {
        "phase": phase,
        "messages": [AIMessage(content=reply)],
    }
    if enriched_movies is not None:
        output["enriched_movies"] = enriched_movies
    if confirmed_movie_data is not None:
        output["confirmed_movie_data"] = confirmed_movie_data

    async def _astream_events(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any]]:
        if emit_tokens:
            yield {
                "event": "on_chat_model_stream",
                "metadata": {"langgraph_node": "presentation"},
                "data": {"chunk": AIMessage(content=reply)},
            }
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {"output": output},
        }

    g = MagicMock()
    g.astream_events = _astream_events
    return g


@asynccontextmanager
async def _noop_lifespan(app: Any) -> AsyncIterator[None]:
    """Bypass the real lifespan so compile_graph() is never called."""
    yield


@pytest.fixture
def mock_graph() -> MagicMock:
    return _make_mock_graph()


@pytest.fixture
def make_mock_graph() -> Any:
    """Fixture that returns the _make_mock_graph factory for parameterised tests."""
    return _make_mock_graph


@pytest.fixture
def noop_lifespan() -> Any:
    """Fixture that returns the _noop_lifespan async context manager."""
    return _noop_lifespan


# ---------------------------------------------------------------------------
# Test HTTP client — no-op lifespan + dependency overrides
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(store: Any, mock_graph: MagicMock) -> AsyncGenerator[httpx.AsyncClient]:
    from app.dependencies import get_graph, get_store
    from app.main import app

    # Override dependencies so routes receive the test store and mock graph.
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_graph] = lambda: mock_graph

    # Swap the lifespan to a no-op so the app starts without chain config.
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as c:
        yield c

    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Convenience fixtures
# ---------------------------------------------------------------------------

_TEST_EMAIL = "user@example.com"
_TEST_PASSWORD = "testpassword123"  # pragma: allowlist secret


@pytest.fixture
async def registered_user(
    client: httpx.AsyncClient,
) -> tuple[str, str, str]:
    """Register a user and return (email, password, access_token)."""
    resp = await client.post(
        "/auth/register",
        json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD},
    )
    assert resp.status_code == 201
    return _TEST_EMAIL, _TEST_PASSWORD, resp.json()["access_token"]


@pytest.fixture
async def auth_headers(registered_user: tuple[str, str, str]) -> dict[str, str]:
    _, _, token = registered_user
    return {"Authorization": f"Bearer {token}"}
