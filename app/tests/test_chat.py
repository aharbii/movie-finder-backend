"""Tests for POST /chat (SSE streaming) and GET /chat/{session_id}/history."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from app.session.store import SessionStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_sse(text: str) -> list[dict[str, Any]]:
    """Extract JSON payloads from an SSE response body."""
    return [
        json.loads(line[len("data: ") :]) for line in text.splitlines() if line.startswith("data: ")
    ]


def new_session_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    async def test_returns_200(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/chat",
            json={"session_id": new_session_id(), "message": "A heist movie"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_content_type_is_sse(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/chat",
            json={"session_id": new_session_id(), "message": "A heist movie"},
            headers=auth_headers,
        )
        assert "text/event-stream" in resp.headers["content-type"]

    async def test_done_event_present(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/chat",
            json={"session_id": new_session_id(), "message": "A heist movie"},
            headers=auth_headers,
        )
        events = parse_sse(resp.text)
        done = next((e for e in events if e.get("type") == "done"), None)
        assert done is not None

    async def test_done_event_contains_required_fields(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        sid = new_session_id()
        resp = await client.post(
            "/chat",
            json={"session_id": sid, "message": "A heist movie"},
            headers=auth_headers,
        )
        done = next(e for e in parse_sse(resp.text) if e.get("type") == "done")
        assert done["session_id"] == sid
        assert "reply" in done
        assert "phase" in done

    async def test_token_events_are_streamed(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Token events should appear before the done event."""
        resp = await client.post(
            "/chat",
            json={"session_id": new_session_id(), "message": "A heist movie"},
            headers=auth_headers,
        )
        events = parse_sse(resp.text)
        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) > 0
        assert all("content" in e for e in token_events)

    async def test_token_events_precede_done_event(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/chat",
            json={"session_id": new_session_id(), "message": "A heist movie"},
            headers=auth_headers,
        )
        events = parse_sse(resp.text)
        types = [e["type"] for e in events]
        assert types[-1] == "done"

    async def test_reply_text_matches_streamed_tokens(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/chat",
            json={"session_id": new_session_id(), "message": "A heist movie"},
            headers=auth_headers,
        )
        events = parse_sse(resp.text)
        token_text = "".join(e["content"] for e in events if e.get("type") == "token")
        done = next(e for e in events if e.get("type") == "done")
        assert done["reply"] == token_text

    async def test_messages_persisted_to_store(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        store: SessionStore,
    ) -> None:
        sid = new_session_id()
        await client.post(
            "/chat",
            json={"session_id": sid, "message": "Inception?"},
            headers=auth_headers,
        )
        messages = await store.get_messages(sid)
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    async def test_session_auto_created_on_first_message(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        store: SessionStore,
    ) -> None:
        sid = new_session_id()
        assert await store.get_session(sid) is None
        await client.post(
            "/chat",
            json={"session_id": sid, "message": "Hello"},
            headers=auth_headers,
        )
        assert await store.get_session(sid) is not None

    async def test_unauthenticated_returns_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/chat",
            json={"session_id": new_session_id(), "message": "Hello"},
        )
        assert resp.status_code == 401

    async def test_wrong_session_owner_returns_403(
        self,
        client: httpx.AsyncClient,
        store: SessionStore,
        registered_user: tuple[str, str, str],
    ) -> None:
        """A session created by another user must not be accessible."""
        # Register a second user and get their token
        resp2 = await client.post(
            "/auth/register",
            json={
                "email": "other@example.com",
                "password": "password123",  # pragma: allowlist secret
            },
        )
        other_token = resp2.json()["access_token"]

        # First user creates a session
        _, _, first_token = registered_user
        sid = new_session_id()
        await client.post(
            "/chat",
            json={"session_id": sid, "message": "Hello"},
            headers={"Authorization": f"Bearer {first_token}"},
        )

        # Second user tries to use the same session ID
        resp = await client.post(
            "/chat",
            json={"session_id": sid, "message": "Hi"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 403

    async def test_confirmation_phase_includes_candidates(
        self,
        store: SessionStore,
        registered_user: tuple[str, str, str],
        make_mock_graph: Any,
        noop_lifespan: Any,
    ) -> None:
        """When graph output has enriched_movies and phase=confirmation, candidates are included."""
        from app.dependencies import get_graph, get_store
        from app.main import app

        candidates = [{"rag_title": "Inception", "imdb_id": "tt1375666", "confidence": 0.9}]
        graph_with_candidates = make_mock_graph(phase="confirmation", enriched_movies=candidates)

        app.dependency_overrides[get_store] = lambda: store
        app.dependency_overrides[get_graph] = lambda: graph_with_candidates
        original = app.router.lifespan_context
        app.router.lifespan_context = noop_lifespan

        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
                base_url="http://test",
            ) as c:
                _, _, token = registered_user
                resp = await c.post(
                    "/chat",
                    json={"session_id": new_session_id(), "message": "Dream movie"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            app.router.lifespan_context = original
            app.dependency_overrides.clear()

        done = next(e for e in parse_sse(resp.text) if e.get("type") == "done")
        assert "candidates" in done
        assert done["candidates"] == candidates

    async def test_fallback_reply_from_messages_when_no_tokens(
        self,
        store: SessionStore,
        registered_user: tuple[str, str, str],
        make_mock_graph: Any,
        noop_lifespan: Any,
    ) -> None:
        """When no token events are emitted, reply is extracted from final state messages."""
        from app.dependencies import get_graph, get_store
        from app.main import app

        graph_no_tokens = make_mock_graph(reply="Fallback reply from state.", emit_tokens=False)

        app.dependency_overrides[get_store] = lambda: store
        app.dependency_overrides[get_graph] = lambda: graph_no_tokens
        original = app.router.lifespan_context
        app.router.lifespan_context = noop_lifespan

        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
                base_url="http://test",
            ) as c:
                _, _, token = registered_user
                resp = await c.post(
                    "/chat",
                    json={"session_id": new_session_id(), "message": "Hello"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            app.router.lifespan_context = original
            app.dependency_overrides.clear()

        done = next(e for e in parse_sse(resp.text) if e.get("type") == "done")
        assert done["reply"] == "Fallback reply from state."


# ---------------------------------------------------------------------------
# GET /chat/{session_id}/history
# ---------------------------------------------------------------------------


class TestChatHistory:
    async def _create_session_with_messages(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        session_id: str,
        messages: list[str],
    ) -> None:
        for msg in messages:
            await client.post(
                "/chat",
                json={"session_id": session_id, "message": msg},
                headers=auth_headers,
            )

    async def test_returns_200_for_own_session(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        sid = new_session_id()
        await self._create_session_with_messages(client, auth_headers, sid, ["Hello"])
        resp = await client.get(f"/chat/{sid}/history", headers=auth_headers)
        assert resp.status_code == 200

    async def test_history_contains_correct_fields(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        sid = new_session_id()
        await self._create_session_with_messages(client, auth_headers, sid, ["Hello"])
        body = (await client.get(f"/chat/{sid}/history", headers=auth_headers)).json()
        assert body["session_id"] == sid
        assert "phase" in body
        assert "messages" in body

    async def test_history_includes_all_turns(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        sid = new_session_id()
        await self._create_session_with_messages(client, auth_headers, sid, ["Turn 1", "Turn 2"])
        body = (await client.get(f"/chat/{sid}/history", headers=auth_headers)).json()
        # Each turn appends one user + one assistant message = 4 total
        assert len(body["messages"]) == 4

    async def test_history_for_nonexistent_session_returns_404(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get(f"/chat/{new_session_id()}/history", headers=auth_headers)
        assert resp.status_code == 404

    async def test_history_for_other_users_session_returns_404(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        # Register another user
        other = await client.post(
            "/auth/register",
            json={
                "email": "other2@example.com",
                "password": "password123",  # pragma: allowlist secret
            },
        )
        other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

        # Other user creates a session
        sid = new_session_id()
        await self._create_session_with_messages(client, other_headers, sid, ["Hi"])

        # Original user tries to read it
        resp = await client.get(f"/chat/{sid}/history", headers=auth_headers)
        assert resp.status_code == 404

    async def test_unauthenticated_returns_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.get(f"/chat/{new_session_id()}/history")
        assert resp.status_code == 401
