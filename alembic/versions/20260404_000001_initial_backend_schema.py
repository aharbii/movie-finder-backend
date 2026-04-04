"""Create initial backend schema with native Postgres types."""

from __future__ import annotations

from collections.abc import Sequence

import alembic.op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260404_000001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create backend tables and supporting indexes."""
    alembic.op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    alembic.op.create_index("ix_users_created_at", "users", ["created_at"], unique=False)

    alembic.op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False, server_default=sa.text("'discovery'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_movie", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    alembic.op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    alembic.op.create_index("ix_sessions_created_at", "sessions", ["created_at"], unique=False)
    alembic.op.create_index("ix_sessions_updated_at", "sessions", ["updated_at"], unique=False)

    alembic.op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    alembic.op.create_index("ix_messages_session_id", "messages", ["session_id"], unique=False)
    alembic.op.create_index("ix_messages_created_at", "messages", ["created_at"], unique=False)

    alembic.op.create_table(
        "refresh_token_blocklist",
        sa.Column("jti", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti"),
    )
    alembic.op.create_index(
        "ix_refresh_token_blocklist_expires_at",
        "refresh_token_blocklist",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop backend tables and supporting indexes."""
    alembic.op.drop_index(
        "ix_refresh_token_blocklist_expires_at", table_name="refresh_token_blocklist"
    )
    alembic.op.drop_table("refresh_token_blocklist")

    alembic.op.drop_index("ix_messages_created_at", table_name="messages")
    alembic.op.drop_index("ix_messages_session_id", table_name="messages")
    alembic.op.drop_table("messages")

    alembic.op.drop_index("ix_sessions_updated_at", table_name="sessions")
    alembic.op.drop_index("ix_sessions_created_at", table_name="sessions")
    alembic.op.drop_index("ix_sessions_user_id", table_name="sessions")
    alembic.op.drop_table("sessions")

    alembic.op.drop_index("ix_users_created_at", table_name="users")
    alembic.op.drop_table("users")
