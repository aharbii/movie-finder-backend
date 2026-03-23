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


class TestGetSessions:
    async def _user(self, store: SessionStore, email: str = "s@example.com") -> str:
        user = await store.create_user(email, "pw")
        return user.id

    async def test_returns_empty_for_new_user(self, store: SessionStore) -> None:
        uid = await self._user(store)
        assert await store.get_sessions(uid) == []

    async def test_returns_sessions_newest_first(self, store: SessionStore) -> None:
        uid = await self._user(store)
        s1 = await store.get_or_create_session("sess-1", uid)
        await store.update_session_phase("sess-1", "confirmation")
        s2 = await store.get_or_create_session("sess-2", uid)
        rows = await store.get_sessions(uid)
        # sess-2 was updated_at more recently
        assert rows[0]["session_id"] == s2["id"]
        assert rows[1]["session_id"] == s1["id"]

    async def test_first_message_is_first_user_message(self, store: SessionStore) -> None:
        uid = await self._user(store)
        await store.get_or_create_session("sess-x", uid)
        await store.append_message("sess-x", "user", "Hello there")
        await store.append_message("sess-x", "assistant", "Hi!")
        await store.append_message("sess-x", "user", "Second message")
        rows = await store.get_sessions(uid)
        assert rows[0]["first_message"] == "Hello there"

    async def test_first_message_null_when_no_messages(self, store: SessionStore) -> None:
        uid = await self._user(store)
        await store.get_or_create_session("sess-empty", uid)
        rows = await store.get_sessions(uid)
        assert rows[0]["first_message"] is None

    async def test_only_returns_sessions_for_owner(self, store: SessionStore) -> None:
        uid1 = await self._user(store, "owner@example.com")
        uid2 = await self._user(store, "other@example.com")
        await store.get_or_create_session("sess-owner", uid1)
        await store.get_or_create_session("sess-other", uid2)
        rows = await store.get_sessions(uid1)
        assert len(rows) == 1
        assert rows[0]["session_id"] == "sess-owner"


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


class TestConfirmedMovie:
    async def _session(self, store: SessionStore) -> str:
        user = await store.create_user("cm@example.com", "pw")
        session = await store.create_session(user.id)
        return session["id"]

    async def test_confirmed_movie_null_by_default(self, store: SessionStore) -> None:
        sid = await self._session(store)
        session = await store.get_session(sid)
        assert session is not None
        assert session.get("confirmed_movie") is None

    async def test_set_confirmed_movie_persists(self, store: SessionStore) -> None:
        sid = await self._session(store)
        data = {"imdb_id": "tt1375666", "imdb_title": "Inception", "imdb_year": 2010}
        await store.set_confirmed_movie(sid, data)
        session = await store.get_session(sid)
        assert session is not None
        assert session["confirmed_movie"] == data

    async def test_confirmed_movie_returned_in_get_sessions(self, store: SessionStore) -> None:
        user = await store.create_user("cm2@example.com", "pw")
        uid = user.id
        session = await store.create_session(uid)
        sid = session["id"]
        data = {"imdb_id": "tt0133093", "imdb_title": "The Matrix", "imdb_year": 1999}
        await store.set_confirmed_movie(sid, data)
        rows = await store.get_sessions(uid)
        assert rows[0]["confirmed_movie"] == data

    async def test_confirmed_movie_null_in_get_sessions_when_unset(
        self, store: SessionStore
    ) -> None:
        user = await store.create_user("cm3@example.com", "pw")
        uid = user.id
        await store.create_session(uid)
        rows = await store.get_sessions(uid)
        assert rows[0].get("confirmed_movie") is None


class TestDeleteSession:
    async def _session_with_messages(self, store: SessionStore) -> tuple[str, str]:
        user = await store.create_user("del@example.com", "pw")
        session = await store.create_session(user.id)
        sid = session["id"]
        await store.append_message(sid, "user", "Hello")
        await store.append_message(sid, "assistant", "Hi!")
        return user.id, sid

    async def test_delete_removes_session(self, store: SessionStore) -> None:
        _, sid = await self._session_with_messages(store)
        await store.delete_session(sid)
        assert await store.get_session(sid) is None

    async def test_delete_removes_messages(self, store: SessionStore) -> None:
        _, sid = await self._session_with_messages(store)
        await store.delete_session(sid)
        assert await store.get_messages(sid) == []

    async def test_delete_removes_from_session_list(self, store: SessionStore) -> None:
        uid, sid = await self._session_with_messages(store)
        await store.delete_session(sid)
        assert await store.get_sessions(uid) == []

    async def test_delete_nonexistent_session_is_noop(self, store: SessionStore) -> None:
        """Deleting a session that doesn't exist should not raise."""
        await store.delete_session("no-such-session")
