"""Tests for the health endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx


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
