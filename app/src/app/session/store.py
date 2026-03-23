"""SQLite-backed session store using aiosqlite.

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

import aiosqlite

from app.auth.models import UserInDB


class SessionStore:
    """Thin async wrapper around an aiosqlite connection."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SessionStore.connect() has not been called")
        return self._db

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def _create_tables(self) -> None:
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id              TEXT PRIMARY KEY,
                email           TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                phase           TEXT NOT NULL DEFAULT 'discovery',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                confirmed_movie TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
        """)
        # Migrate existing databases that predate the confirmed_movie column.
        # SQLite does not support ALTER TABLE … ADD COLUMN IF NOT EXISTS, so we
        # attempt it and ignore the error when the column already exists.
        try:
            await self._conn.execute("ALTER TABLE sessions ADD COLUMN confirmed_movie TEXT")
            await self._conn.commit()
        except Exception:
            pass  # column already present — nothing to do

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    async def create_user(self, email: str, hashed_password: str) -> UserInDB:
        user_id = str(uuid.uuid4())
        now = _now()
        await self._conn.execute(
            "INSERT INTO users (id, email, hashed_password, created_at) VALUES (?, ?, ?, ?)",
            (user_id, email, hashed_password, now),
        )
        await self._conn.commit()
        return UserInDB(id=user_id, email=email, hashed_password=hashed_password, created_at=now)

    async def get_user_by_email(self, email: str) -> UserInDB | None:
        async with self._conn.execute(
            "SELECT id, email, hashed_password, created_at FROM users WHERE email = ?",
            (email,),
        ) as cur:
            row = await cur.fetchone()
        return _row_to_user(row)

    async def get_user_by_id(self, user_id: str) -> UserInDB | None:
        async with self._conn.execute(
            "SELECT id, email, hashed_password, created_at FROM users WHERE id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return _row_to_user(row)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def create_session(self, user_id: str) -> dict[str, Any]:
        return await self._upsert_session(str(uuid.uuid4()), user_id)

    async def get_or_create_session(self, session_id: str, user_id: str) -> dict[str, Any]:
        """Return existing session or create a new one with the given ID."""
        existing = await self.get_session(session_id)
        if existing is not None:
            return existing
        return await self._upsert_session(session_id, user_id)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        async with self._conn.execute(
            "SELECT id, user_id, phase, created_at, updated_at, confirmed_movie FROM sessions WHERE id = ?",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        if result.get("confirmed_movie"):
            result["confirmed_movie"] = json.loads(result["confirmed_movie"])
        return result

    async def get_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Return all sessions for *user_id*, newest first, with first user message."""
        async with self._conn.execute(
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
            WHERE  s.user_id = ?
            ORDER  BY s.updated_at DESC
            """,
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
        results = []
        for row in rows:
            r = dict(row)
            if r.get("confirmed_movie"):
                r["confirmed_movie"] = json.loads(r["confirmed_movie"])
            results.append(r)
        return results

    async def update_session_phase(self, session_id: str, phase: str) -> None:
        await self._conn.execute(
            "UPDATE sessions SET phase = ?, updated_at = ? WHERE id = ?",
            (phase, _now(), session_id),
        )
        await self._conn.commit()

    async def set_confirmed_movie(self, session_id: str, data: dict[str, Any]) -> None:
        await self._conn.execute(
            "UPDATE sessions SET confirmed_movie = ?, updated_at = ? WHERE id = ?",
            (json.dumps(data), _now(), session_id),
        )
        await self._conn.commit()

    async def _upsert_session(self, session_id: str, user_id: str) -> dict[str, Any]:
        now = _now()
        await self._conn.execute(
            "INSERT INTO sessions (id, user_id, phase, created_at, updated_at)"
            " VALUES (?, ?, 'discovery', ?, ?)",
            (session_id, user_id, now, now),
        )
        await self._conn.commit()
        return {
            "id": session_id,
            "user_id": user_id,
            "phase": "discovery",
            "created_at": now,
            "updated_at": now,
        }

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        await self._conn.execute(
            "INSERT INTO messages (id, session_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), session_id, role, content, _now()),
        )
        await self._conn.commit()

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        async with self._conn.execute(
            "SELECT id, session_id, role, content, created_at"
            " FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_user(row: aiosqlite.Row | None) -> UserInDB | None:
    if row is None:
        return None
    return UserInDB(
        id=row["id"],
        email=row["email"],
        hashed_password=row["hashed_password"],
        created_at=row["created_at"],
    )
