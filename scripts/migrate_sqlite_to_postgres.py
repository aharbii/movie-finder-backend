#!/usr/bin/env python3
"""Migrate movie_finder.db (SQLite) to a PostgreSQL database.

Usage
-----
    # Run from backend/ through the Docker-only backend contract:
    docker compose run --rm backend python scripts/migrate_sqlite_to_postgres.py [sqlite_path]

    # Or with an explicit target database:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname \\ # pragma: allowlist secret
        docker compose run --rm backend \
            python scripts/migrate_sqlite_to_postgres.py movie_finder.db

Environment variables
---------------------
DATABASE_URL   PostgreSQL connection string (required, or set in .env).
               Defaults to: postgresql://postgres:postgres@localhost:5432/movie_finder # pragma: allowlist secret

The script is idempotent — rows that already exist in the target database
(matched by primary key) are silently skipped.  Safe to run multiple times.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from pathlib import Path


async def _migrate(sqlite_path: str, pg_url: str) -> None:
    import asyncpg  # noqa: PLC0415 (late import so error is clear when missing)

    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row

    print(f"Source : {sqlite_path}")
    print(f"Target : {pg_url}\n")

    pool: asyncpg.Pool[asyncpg.Record] = await asyncpg.create_pool(pg_url)

    # ------------------------------------------------------------------
    # Ensure schema exists in the target (same DDL as SessionStore)
    # ------------------------------------------------------------------
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              TEXT PRIMARY KEY,
                email           TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at      TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                phase           TEXT NOT NULL DEFAULT 'discovery',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                confirmed_movie TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id         TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

    # ------------------------------------------------------------------
    # Migrate users
    # ------------------------------------------------------------------
    users = src.execute("SELECT id, email, hashed_password, created_at FROM users").fetchall()
    inserted = skipped = 0
    async with pool.acquire() as conn:
        for row in users:
            try:
                await conn.execute(
                    "INSERT INTO users (id, email, hashed_password, created_at)"
                    " VALUES ($1, $2, $3, $4)",
                    row["id"],
                    row["email"],
                    row["hashed_password"],
                    row["created_at"],
                )
                inserted += 1
            except asyncpg.UniqueViolationError:
                skipped += 1
    print(f"users    : {inserted} inserted, {skipped} skipped (already exist)")

    # ------------------------------------------------------------------
    # Migrate sessions
    # ------------------------------------------------------------------
    sessions = src.execute(
        "SELECT id, user_id, phase, created_at, updated_at, confirmed_movie FROM sessions"
    ).fetchall()
    inserted = skipped = 0
    async with pool.acquire() as conn:
        for row in sessions:
            try:
                await conn.execute(
                    "INSERT INTO sessions"
                    " (id, user_id, phase, created_at, updated_at, confirmed_movie)"
                    " VALUES ($1, $2, $3, $4, $5, $6)",
                    row["id"],
                    row["user_id"],
                    row["phase"],
                    row["created_at"],
                    row["updated_at"],
                    row["confirmed_movie"],  # already a JSON string or None — pass as-is
                )
                inserted += 1
            except asyncpg.UniqueViolationError:
                skipped += 1
    print(f"sessions : {inserted} inserted, {skipped} skipped (already exist)")

    # ------------------------------------------------------------------
    # Migrate messages
    # ------------------------------------------------------------------
    messages = src.execute(
        "SELECT id, session_id, role, content, created_at FROM messages"
    ).fetchall()
    inserted = skipped = 0
    async with pool.acquire() as conn:
        for row in messages:
            try:
                await conn.execute(
                    "INSERT INTO messages (id, session_id, role, content, created_at)"
                    " VALUES ($1, $2, $3, $4, $5)",
                    row["id"],
                    row["session_id"],
                    row["role"],
                    row["content"],
                    row["created_at"],
                )
                inserted += 1
            except asyncpg.UniqueViolationError:
                skipped += 1
    print(f"messages : {inserted} inserted, {skipped} skipped (already exist)")

    await pool.close()
    src.close()
    print("\nMigration complete.")


def main() -> None:
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else "movie_finder.db"

    if not Path(sqlite_path).exists():
        print(f"Error: SQLite file not found: {sqlite_path}", file=sys.stderr)
        sys.exit(1)

    # Load .env if present so DATABASE_URL can be set there
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

    pg_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/movie_finder",  # pragma: allowlist secret
    )

    asyncio.run(_migrate(sqlite_path, pg_url))


if __name__ == "__main__":
    main()
