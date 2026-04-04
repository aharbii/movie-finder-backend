"""PostgreSQL-backed session store using asyncpg.

Manages three tables:
  users    — registered accounts
  sessions — conversation threads (maps 1-to-1 with a LangGraph thread_id)
  messages — full chat history per session (persisted independently of the
             in-memory LangGraph checkpointer so history survives restarts)
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg

from app.auth.models import UserInDB


class SessionStore:
    """Async wrapper around an asyncpg connection pool."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool[asyncpg.Record] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the asyncpg pool and register per-connection codecs."""
        self._pool = await asyncpg.create_pool(self._database_url, init=_init_connection)
        await self.purge_expired_refresh_tokens()

    async def close(self) -> None:
        """Close the asyncpg pool if it is open."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def ping(self) -> None:
        """Verify that the backing database pool can serve a simple query."""
        async with self._p.acquire() as conn:
            await conn.execute("SELECT 1")

    @property
    def _p(self) -> asyncpg.Pool[asyncpg.Record]:
        if self._pool is None:
            raise RuntimeError("SessionStore.connect() has not been called")
        return self._pool

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    async def create_user(self, email: str, hashed_password: str) -> UserInDB:
        """Create and persist a new user record."""
        user_id = uuid.uuid4()
        now = _now()
        async with self._p.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (id, email, hashed_password, created_at)"
                " VALUES ($1, $2, $3, $4)",
                user_id,
                email,
                hashed_password,
                now,
            )
        return UserInDB(
            id=str(user_id),
            email=email,
            hashed_password=hashed_password,
            created_at=_serialize_value(now),
        )

    async def get_user_by_email(self, email: str) -> UserInDB | None:
        """Fetch a user by email address."""
        async with self._p.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, hashed_password, created_at FROM users WHERE email = $1",
                email,
            )
        return _row_to_user(row)

    async def get_user_by_id(self, user_id: str) -> UserInDB | None:
        """Fetch a user by UUID string."""
        user_uuid = _try_parse_uuid(user_id)
        if user_uuid is None:
            return None
        async with self._p.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, hashed_password, created_at FROM users WHERE id = $1",
                user_uuid,
            )
        return _row_to_user(row)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def create_session(self, user_id: str) -> dict[str, Any]:
        """Create a new chat session for a user."""
        return await self._upsert_session(str(uuid.uuid4()), user_id)

    async def get_or_create_session(self, session_id: str, user_id: str) -> dict[str, Any]:
        """Return existing session or create a new one with the given ID."""
        existing = await self.get_session(session_id)
        if existing is not None:
            return existing
        return await self._upsert_session(session_id, user_id)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Fetch a session by UUID string."""
        session_uuid = _try_parse_uuid(session_id)
        if session_uuid is None:
            return None
        async with self._p.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, user_id, phase, created_at, updated_at, confirmed_movie"
                " FROM sessions WHERE id = $1",
                session_uuid,
            )
        if row is None:
            return None
        return _serialize_record(row)

    async def get_sessions(self, user_id: str, limit: int, offset: int) -> dict[str, Any]:
        """Return a paginated session listing for a user."""
        user_uuid = _try_parse_uuid(user_id)
        if user_uuid is None:
            return {"total": 0, "limit": limit, "offset": offset, "items": []}
        async with self._p.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM sessions WHERE user_id = $1",
                user_uuid,
            )
            rows = await conn.fetch(
                """
                SELECT
                    s.id              AS session_id,
                    s.phase,
                    s.updated_at,
                    s.confirmed_movie,
                    (
                        SELECT m.content
                        FROM   messages m
                        WHERE  m.session_id = s.id
                          AND  m.role = 'user'
                        ORDER  BY m.created_at
                        LIMIT  1
                    ) AS first_message
                FROM   sessions s
                WHERE  s.user_id = $1
                ORDER  BY s.created_at DESC
                LIMIT  $2
                OFFSET $3
                """,
                user_uuid,
                limit,
                offset,
            )
        return {
            "total": int(total or 0),
            "limit": limit,
            "offset": offset,
            "items": [_serialize_record(row) for row in rows],
        }

    async def update_session_phase(self, session_id: str, phase: str) -> None:
        """Update the persisted phase for a session."""
        session_uuid = _try_parse_uuid(session_id)
        if session_uuid is None:
            return
        async with self._p.acquire() as conn:
            await conn.execute(
                "UPDATE sessions SET phase = $1, updated_at = $2 WHERE id = $3",
                phase,
                _now(),
                session_uuid,
            )

    async def set_confirmed_movie(self, session_id: str, data: dict[str, Any]) -> None:
        """Persist the confirmed movie payload for a session."""
        session_uuid = _try_parse_uuid(session_id)
        if session_uuid is None:
            return
        async with self._p.acquire() as conn:
            await conn.execute(
                "UPDATE sessions SET confirmed_movie = $1, updated_at = $2 WHERE id = $3",
                data,
                _now(),
                session_uuid,
            )

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and all persisted messages."""
        session_uuid = _try_parse_uuid(session_id)
        if session_uuid is None:
            return
        async with self._p.acquire() as conn:
            await conn.execute("DELETE FROM messages WHERE session_id = $1", session_uuid)
            await conn.execute("DELETE FROM sessions WHERE id = $1", session_uuid)

    async def revoke_refresh_token(self, jti: str, expires_at: datetime) -> None:
        """Insert or refresh a revoked refresh-token JTI entry."""
        async with self._p.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO refresh_token_blocklist (jti, expires_at)
                VALUES ($1, $2)
                ON CONFLICT (jti)
                DO UPDATE SET expires_at = GREATEST(
                    refresh_token_blocklist.expires_at,
                    EXCLUDED.expires_at
                )
                """,
                jti,
                expires_at,
            )

    async def is_refresh_token_revoked(self, jti: str) -> bool:
        """Return whether a refresh-token JTI is currently blocklisted."""
        await self.purge_expired_refresh_tokens()
        async with self._p.acquire() as conn:
            row = await conn.fetchval(
                "SELECT 1 FROM refresh_token_blocklist WHERE jti = $1",
                jti,
            )
        return bool(row)

    async def purge_expired_refresh_tokens(self) -> None:
        """Remove expired refresh-token blocklist entries."""
        async with self._p.acquire() as conn:
            await conn.execute(
                "DELETE FROM refresh_token_blocklist WHERE expires_at <= $1",
                _now(),
            )

    async def _upsert_session(self, session_id: str, user_id: str) -> dict[str, Any]:
        """Create a new session row with a caller-supplied UUID."""
        now = _now()
        session_uuid = _parse_uuid(session_id)
        user_uuid = _parse_uuid(user_id)
        async with self._p.acquire() as conn:
            await conn.execute(
                "INSERT INTO sessions (id, user_id, phase, created_at, updated_at)"
                " VALUES ($1, $2, 'discovery', $3, $4)",
                session_uuid,
                user_uuid,
                now,
                now,
            )
        return {
            "id": str(session_uuid),
            "user_id": str(user_uuid),
            "phase": "discovery",
            "created_at": _serialize_value(now),
            "updated_at": _serialize_value(now),
        }

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        """Append a persisted chat message to a session."""
        session_uuid = _try_parse_uuid(session_id)
        if session_uuid is None:
            return
        async with self._p.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (id, session_id, role, content, created_at)"
                " VALUES ($1, $2, $3, $4, $5)",
                uuid.uuid4(),
                session_uuid,
                role,
                content,
                _now(),
            )

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Return all messages for a session in chronological order."""
        session_uuid = _try_parse_uuid(session_id)
        if session_uuid is None:
            return []
        async with self._p.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, session_id, role, content, created_at"
                " FROM messages WHERE session_id = $1 ORDER BY created_at",
                session_uuid,
            )
        return [_serialize_record(r) for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register asyncpg JSONB codecs for each pooled connection."""
    await conn.set_type_codec(
        "jsonb",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
    )


def _serialize_record(row: asyncpg.Record) -> dict[str, Any]:
    """Convert asyncpg records into JSON-serializable dictionaries."""
    return {key: _serialize_value(value) for key, value in row.items()}


def _serialize_value(value: Any) -> Any:
    """Normalize asyncpg-native values to API-safe Python primitives."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat()
    return value


def _try_parse_uuid(value: str) -> UUID | None:
    """Parse a UUID string, returning None for invalid input."""
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _parse_uuid(value: str) -> UUID:
    """Parse a UUID string or raise a ValueError."""
    parsed = _try_parse_uuid(value)
    if parsed is None:
        raise ValueError(f"Invalid UUID value: {value}")
    return parsed


def _row_to_user(row: asyncpg.Record | None) -> UserInDB | None:
    """Convert a database row into a UserInDB model."""
    if row is None:
        return None
    return UserInDB(
        id=_serialize_value(row["id"]),
        email=row["email"],
        hashed_password=row["hashed_password"],
        created_at=_serialize_value(row["created_at"]),
    )
