"""Tests for the health endpoints."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace, TracebackType
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI


class TestHealth:
    async def test_health_alias_returns_200(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_live_returns_ok_status(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/health/live")
        assert resp.json() == {"status": "ok"}

    async def test_ready_returns_ok_status(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/health/ready")
        assert resp.json() == {"status": "ok"}

    async def test_ready_returns_503_if_store_unavailable(self, client: httpx.AsyncClient) -> None:
        """Simulate store unavailability by overriding the dependency to raise an exception."""
        from app.dependencies import get_store
        from app.main import app

        mock_store = MagicMock()
        mock_store.ping = AsyncMock(side_effect=Exception("DB down"))
        app.dependency_overrides[get_store] = lambda: mock_store

        try:
            resp = await client.get("/health/ready")
            assert resp.status_code == 503
            assert resp.json() == {"detail": "Session store unavailable"}

            mock_store.ping.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    async def test_health_endpoints_require_no_auth(self, client: httpx.AsyncClient) -> None:
        """Health endpoints must be reachable without a token."""
        resp = await client.get("/health/live")
        assert resp.status_code != 401

    async def test_lifespan_owns_shared_checkpointer(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The backend should create, inject, and close one shared checkpointer."""
        from app import main

        fake_store = MagicMock()
        fake_store.connect = AsyncMock()
        fake_store.close = AsyncMock()

        fake_checkpointer = object()
        fake_graph = object()

        class FakeCheckpointerContext(
            AbstractAsyncContextManager[object],
        ):
            """Minimal async context manager used to verify startup wiring."""

            def __init__(self) -> None:
                """Initialize enter/exit tracking for the fake checkpointer."""
                self.entered = False
                self.exited = False

            async def __aenter__(self) -> object:
                """Return the fake shared checkpointer."""
                self.entered = True
                return fake_checkpointer

            async def __aexit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: TracebackType | None,
            ) -> None:
                """Record that the checkpointer was closed cleanly."""
                self.exited = True

        fake_context = FakeCheckpointerContext()
        captured: dict[str, object] = {}
        app = FastAPI()

        monkeypatch.setattr(
            main,
            "get_config",
            lambda: SimpleNamespace(
                app_env="test",
                app_port=8000,
                database_url="postgresql://movie_finder:devpassword@postgres:5432/movie_finder",  # pragma: allowlist secret
            ),
        )
        monkeypatch.setattr(main, "SessionStore", lambda database_url: fake_store)
        monkeypatch.setattr(main, "checkpoint_lifespan", lambda database_url: fake_context)
        monkeypatch.setattr(main, "compile_graph", lambda checkpointer: fake_graph)
        monkeypatch.setattr(main, "configure_chain_runtime", lambda config: None)
        monkeypatch.setattr(main, "set_store", lambda store: captured.setdefault("store", store))
        monkeypatch.setattr(main, "set_graph", lambda graph: captured.setdefault("graph", graph))

        async with main.lifespan(app):
            assert fake_context.entered is True
            assert app.state.checkpointer_context is fake_context
            assert app.state.checkpointer is fake_checkpointer
            assert captured["store"] is fake_store
            assert captured["graph"] is fake_graph

        fake_store.connect.assert_awaited_once()
        fake_store.close.assert_awaited_once()
        assert fake_context.exited is True
