"""Application configuration via Pydantic Settings.

Reads from environment variables / .env file.  Fail-fast on first import
so misconfigured deployments surface immediately.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
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
    # Accepts bare path (./movie_finder.db) or SQLAlchemy-style URL
    # (sqlite+aiosqlite:///./movie_finder.db).  The store strips the prefix.
    database_url: str = Field(
        default="./movie_finder.db",
        description="SQLite path or sqlite+aiosqlite:/// URL",
    )

    # --- JWT lifetimes ---
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    @property
    def sqlite_path(self) -> str:
        """Return the bare file path regardless of URL format."""
        prefix = "sqlite+aiosqlite:///"
        if self.database_url.startswith(prefix):
            return self.database_url[len(prefix) :]
        return self.database_url


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Return the singleton AppConfig (cached after first call)."""
    return AppConfig()  # type: ignore[call-arg]
