"""Unit tests for SessionStore CRUD operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from app.session.store import SessionStore


def new_uuid() -> str:
    """Return a fresh UUID string for test data."""
    return str(uuid.uuid4())


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
        with pytest.raises(asyncpg.UniqueViolationError):
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
        session_id = new_uuid()
        session = await store.get_or_create_session(session_id, uid)
        assert session["id"] == session_id
        assert session["phase"] == "discovery"

    async def test_get_or_create_returns_existing_session(self, store: SessionStore) -> None:
        uid = await self._user(store)
        session_id = new_uuid()
        first = await store.get_or_create_session(session_id, uid)
        await store.update_session_phase(session_id, "qa")
        second = await store.get_or_create_session(session_id, uid)
        # Should return existing session, not reset phase
        assert second["id"] == first["id"]
        assert second["phase"] == "qa"


class TestGetSessions:
    async def _user(self, store: SessionStore, email: str = "s@example.com") -> str:
        user = await store.create_user(email, "pw")
        return user.id

    async def test_returns_empty_for_new_user(self, store: SessionStore) -> None:
        uid = await self._user(store)
        assert await store.get_sessions(uid, limit=20, offset=0) == {
            "total": 0,
            "limit": 20,
            "offset": 0,
            "items": [],
        }

    async def test_returns_sessions_newest_first(self, store: SessionStore) -> None:
        uid = await self._user(store)
        s1 = await store.get_or_create_session(new_uuid(), uid)
        await store.update_session_phase(s1["id"], "confirmation")
        s2 = await store.get_or_create_session(new_uuid(), uid)
        rows = await store.get_sessions(uid, limit=20, offset=0)
        # sess-2 was updated_at more recently
        assert rows["items"][0]["session_id"] == s2["id"]
        assert rows["items"][1]["session_id"] == s1["id"]

    async def test_first_message_is_first_user_message(self, store: SessionStore) -> None:
        uid = await self._user(store)
        session_id = new_uuid()
        await store.get_or_create_session(session_id, uid)
        await store.append_message(session_id, "user", "Hello there")
        await store.append_message(session_id, "assistant", "Hi!")
        await store.append_message(session_id, "user", "Second message")
        rows = await store.get_sessions(uid, limit=20, offset=0)
        assert rows["items"][0]["first_message"] == "Hello there"

    async def test_first_message_null_when_no_messages(self, store: SessionStore) -> None:
        uid = await self._user(store)
        await store.get_or_create_session(new_uuid(), uid)
        rows = await store.get_sessions(uid, limit=20, offset=0)
        assert rows["items"][0]["first_message"] is None

    async def test_only_returns_sessions_for_owner(self, store: SessionStore) -> None:
        uid1 = await self._user(store, "owner@example.com")
        uid2 = await self._user(store, "other@example.com")
        owner_session = await store.get_or_create_session(new_uuid(), uid1)
        await store.get_or_create_session(new_uuid(), uid2)
        rows = await store.get_sessions(uid1, limit=20, offset=0)
        assert rows["total"] == 1
        assert rows["items"][0]["session_id"] == owner_session["id"]

    async def test_pagination_respects_limit_and_offset(self, store: SessionStore) -> None:
        uid = await self._user(store)
        sessions = [await store.get_or_create_session(new_uuid(), uid) for _ in range(3)]
        page = await store.get_sessions(uid, limit=1, offset=1)
        assert page["total"] == 3
        assert page["limit"] == 1
        assert page["offset"] == 1
        assert len(page["items"]) == 1
        assert page["items"][0]["session_id"] == sessions[1]["id"]


class TestMessages:
    async def _session(self, store: SessionStore) -> str | Any:
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
    async def _session(self, store: SessionStore) -> str | Any:
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
        rows = await store.get_sessions(uid, limit=20, offset=0)
        assert rows["items"][0]["confirmed_movie"] == data

    async def test_confirmed_movie_null_in_get_sessions_when_unset(
        self, store: SessionStore
    ) -> None:
        user = await store.create_user("cm3@example.com", "pw")
        uid = user.id
        await store.create_session(uid)
        rows = await store.get_sessions(uid, limit=20, offset=0)
        assert rows["items"][0].get("confirmed_movie") is None


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
        assert await store.get_sessions(uid, limit=20, offset=0) == {
            "total": 0,
            "limit": 20,
            "offset": 0,
            "items": [],
        }

    async def test_delete_nonexistent_session_is_noop(self, store: SessionStore) -> None:
        """Deleting a session that doesn't exist should not raise."""
        await store.delete_session("no-such-session")


class TestRefreshTokenBlocklist:
    async def test_revoke_refresh_token_marks_it_revoked(self, store: SessionStore) -> None:
        expires_at = datetime.now(UTC) + timedelta(days=1)
        await store.revoke_refresh_token("refresh-jti", expires_at)
        assert await store.is_refresh_token_revoked("refresh-jti") is True

    async def test_purge_expired_refresh_tokens_removes_old_entries(
        self, store: SessionStore
    ) -> None:
        expires_at = datetime.now(UTC) - timedelta(minutes=5)
        await store.revoke_refresh_token("expired-jti", expires_at)
        await store.purge_expired_refresh_tokens()
        assert await store.is_refresh_token_revoked("expired-jti") is False


class TestSchema:
    async def test_schema_uses_native_postgres_types(self, store: SessionStore) -> None:
        async with store._p.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    table_name,
                    column_name,
                    data_type,
                    udt_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND (
                    (table_name = 'users' AND column_name = 'id')
                    OR (table_name = 'sessions' AND column_name IN ('id', 'user_id', 'confirmed_movie'))
                    OR (table_name = 'messages' AND column_name = 'created_at')
                  )
                ORDER BY table_name, column_name
                """
            )

        columns = {
            (row["table_name"], row["column_name"]): (row["data_type"], row["udt_name"])
            for row in rows
        }
        assert columns[("users", "id")] == ("uuid", "uuid")
        assert columns[("sessions", "id")] == ("uuid", "uuid")
        assert columns[("sessions", "user_id")] == ("uuid", "uuid")
        assert columns[("sessions", "confirmed_movie")] == ("jsonb", "jsonb")
        assert columns[("messages", "created_at")] == ("timestamp with time zone", "timestamptz")

    async def test_schema_creates_expected_indexes(self, store: SessionStore) -> None:
        async with store._p.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname IN (
                    'ix_sessions_user_id',
                    'ix_sessions_created_at',
                    'ix_sessions_updated_at',
                    'ix_messages_created_at',
                    'ix_refresh_token_blocklist_expires_at'
                  )
                """
            )

        index_names = {row["indexname"] for row in rows}
        assert index_names == {
            "ix_sessions_user_id",
            "ix_sessions_created_at",
            "ix_sessions_updated_at",
            "ix_messages_created_at",
            "ix_refresh_token_blocklist_expires_at",
        }
