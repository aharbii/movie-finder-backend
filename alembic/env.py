"""Alembic environment configuration for backend schema migrations."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

import alembic.context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

config = alembic.context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _resolve_database_url() -> str:
    """Return the configured database URL using SQLAlchemy's asyncpg dialect."""
    url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("DATABASE_URL must be set before running Alembic migrations")
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    alembic.context.configure(
        url=_resolve_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with alembic.context.begin_transaction():
        alembic.context.run_migrations()


def _run_migrations(connection: object) -> None:
    """Run migrations against an already-open SQLAlchemy connection."""
    alembic.context.configure(connection=connection, target_metadata=target_metadata)

    with alembic.context.begin_transaction():
        alembic.context.run_migrations()


async def _run_async_migrations() -> None:
    """Open an async SQLAlchemy engine and run migrations online."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _resolve_database_url()
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    asyncio.run(_run_async_migrations())


if alembic.context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
