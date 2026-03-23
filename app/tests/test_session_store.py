"""Unit tests for SessionStore CRUD operations."""

from __future__ import annotations

import sqlite3

import pytest

from app.session.store import SessionStore


class TestUsers:
    async def test_create_user_returns_user_in_db(self, store: SessionStore) -> None:
        user = await store.create_user("alice@example.com", "hashed_pw")
        assert user.email == "alice@example.com"
        assert user.hashed_password == "hashed_pw"  # pragma: allowlist secret
        assert user.id  # non-empty UUID

    async def test_get_user_by_email_found(self, store: SessionStore) -> None:
        await store.create_user("bob@example.com", "hashed_pw")
        user = await store.get_user_by_email("bob@example.com")
        assert user is not None
        assert user.email == "bob@example.com"

    async def test_get_user_by_email_not_found(self, store: SessionStore) -> None:
        result = await store.get_user_by_email("ghost@example.com")
        assert result is None

    async def test_get_user_by_id_found(self, store: SessionStore) -> None:
        created = await store.create_user("charlie@example.com", "hashed_pw")
        user = await store.get_user_by_id(created.id)
        assert user is not None
        assert user.id == created.id

    async def test_get_user_by_id_not_found(self, store: SessionStore) -> None:
        result = await store.get_user_by_id("00000000-0000-0000-0000-000000000000")
        assert result is None

    async def test_duplicate_email_raises(self, store: SessionStore) -> None:
        await store.create_user("dup@example.com", "hashed_pw")
        with pytest.raises(sqlite3.IntegrityError):
            await store.create_user("dup@example.com", "other_pw")


class TestSessions:
    async def _user(self, store: SessionStore) -> str:
        user = await store.create_user("u@example.com", "pw")
        return user.id

    async def test_create_session_returns_discovery_phase(self, store: SessionStore) -> None:
        uid = await self._user(store)
        session = await store.create_session(uid)
        assert session["phase"] == "discovery"
        assert session["user_id"] == uid
        assert session["id"]

    async def test_get_session_found(self, store: SessionStore) -> None:
        uid = await self._user(store)
        created = await store.create_session(uid)
        fetched = await store.get_session(created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]

    async def test_get_session_not_found(self, store: SessionStore) -> None:
        result = await store.get_session("no-such-session")
        assert result is None

    async def test_update_session_phase(self, store: SessionStore) -> None:
        uid = await self._user(store)
        session = await store.create_session(uid)
        await store.update_session_phase(session["id"], "confirmation")
        updated = await store.get_session(session["id"])
        assert updated is not None
        assert updated["phase"] == "confirmation"

    async def test_get_or_create_creates_new_session(self, store: SessionStore) -> None:
        uid = await self._user(store)
        session = await store.get_or_create_session("new-session-id", uid)
        assert session["id"] == "new-session-id"
        assert session["phase"] == "discovery"

    async def test_get_or_create_returns_existing_session(self, store: SessionStore) -> None:
        uid = await self._user(store)
        first = await store.get_or_create_session("sess-abc", uid)
        await store.update_session_phase("sess-abc", "qa")
        second = await store.get_or_create_session("sess-abc", uid)
        # Should return existing session, not reset phase
        assert second["id"] == first["id"]
        assert second["phase"] == "qa"


class TestMessages:
    async def _session(self, store: SessionStore) -> str:
        user = await store.create_user("m@example.com", "pw")
        session = await store.create_session(user.id)
        return session["id"]

    async def test_append_and_retrieve_messages(self, store: SessionStore) -> None:
        sid = await self._session(store)
        await store.append_message(sid, "user", "Hello")
        await store.append_message(sid, "assistant", "Hi there!")
        messages = await store.get_messages(sid)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"

    async def test_get_messages_empty_for_new_session(self, store: SessionStore) -> None:
        sid = await self._session(store)
        assert await store.get_messages(sid) == []

    async def test_messages_ordered_chronologically(self, store: SessionStore) -> None:
        sid = await self._session(store)
        for i in range(5):
            await store.append_message(sid, "user", f"msg-{i}")
        messages = await store.get_messages(sid)
        contents = [m["content"] for m in messages]
        assert contents == [f"msg-{i}" for i in range(5)]
