"""Tests for the /health liveness probe."""

from __future__ import annotations

import httpx


class TestHealth:
    async def test_returns_200(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_returns_ok_status(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.json() == {"status": "ok"}

    async def test_no_auth_required(self, client: httpx.AsyncClient) -> None:
        """Health endpoint must be reachable without a token."""
        resp = await client.get("/health")
        assert resp.status_code != 401
