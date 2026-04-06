"""Application configuration via Pydantic Settings.

Reads from environment variables / .env file.  Fail-fast on first import
so misconfigured deployments surface immediately.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Environment-driven configuration for the Movie Finder FastAPI app."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_env: str = Field(default="development", description="development | staging | production")
    app_port: int = Field(default=8000, ge=1, le=65535)

    # --- Security ---
    app_secret_key: str = Field(..., description="JWT signing secret (openssl rand -hex 32)")

    # --- Database ---
    # PostgreSQL connection URL: postgresql://user:password@host:5432/dbname # pragma: allowlist secret
    database_url: str = Field(
        ...,
        description="PostgreSQL connection URL (postgresql://user:pass@host:port/db)",  # pragma: allowlist secret
    )

    # --- HTTP / API ---
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:4200"],
        description="Allowed browser origins for CORS",
    )
    global_rate_limit: str = Field(default="100/minute")
    auth_rate_limit: str = Field(default="5/minute")
    chat_rate_limit: str = Field(default="20/minute")
    max_message_length: int = Field(default=2000, ge=1)

    # --- JWT lifetimes ---
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _coerce_cors_origins(cls, value: Any) -> Any:
        """Accept JSON-array or comma-separated CORS origin configuration."""
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            if not stripped:
                return []
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Return the singleton AppConfig (cached after first call)."""
    return AppConfig()
