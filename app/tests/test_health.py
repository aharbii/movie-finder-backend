"""Tests for the health endpoints."""

from __future__ import annotations

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

    async def test_health_endpoints_require_no_auth(self, client: httpx.AsyncClient) -> None:
        """Health endpoints must be reachable without a token."""
        resp = await client.get("/health/live")
        assert resp.status_code != 401
