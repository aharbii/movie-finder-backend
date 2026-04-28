"""Application configuration via Pydantic Settings.

Reads from environment variables / .env file.  Fail-fast on first import
so misconfigured deployments surface immediately.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, cast

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from chain.config import ChainConfig, ChatProvider, EmbeddingProvider, VectorStoreProvider


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

    # --- Chain provider runtime ---
    classifier_provider: ChatProvider = Field(default="anthropic")
    classifier_model: str = Field(default="claude-haiku-4-5-20251001")
    reasoning_provider: ChatProvider = Field(default="anthropic")
    reasoning_model: str = Field(default="claude-sonnet-4-6")
    embedding_provider: EmbeddingProvider = Field(default="openai")
    embedding_model: str = Field(default="text-embedding-3-large")
    embedding_dimension: int = Field(default=3072, ge=1)
    vector_store: VectorStoreProvider = Field(default="qdrant")
    vector_collection_prefix: str = Field(default="movies")

    # --- Chain provider credentials and endpoints ---
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    together_api_key: str | None = None
    google_api_key: str | None = None
    ollama_base_url: str = Field(default="http://localhost:11434")
    qdrant_url: str | None = None
    qdrant_api_key_ro: str | None = None
    chromadb_persist_path: str = Field(default="outputs/chromadb/local")
    pinecone_api_key: str | None = None
    pinecone_index_name: str = Field(default="movie-finder-rag")
    pinecone_index_host: str | None = None
    pinecone_cloud: str = Field(default="aws")
    pinecone_region: str = Field(default="us-east-1")
    pgvector_dsn: str | None = None
    pgvector_schema: str = Field(default="public")

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

    @field_validator(
        "ollama_base_url",
        "qdrant_url",
        "pinecone_index_host",
        mode="before",
    )
    @classmethod
    def _strip_optional_url(cls, value: str | None) -> str | None:
        """Normalize optional provider URLs before passing them to chain."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped.rstrip("/") if stripped else None

    @field_validator("vector_collection_prefix")
    @classmethod
    def _validate_vector_collection_prefix(cls, value: str) -> str:
        """Reject blank dynamic vector collection prefixes."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("VECTOR_COLLECTION_PREFIX must not be blank")
        return stripped

    def to_chain_config(self) -> ChainConfig:
        """Build the chain runtime config from validated backend settings."""
        values: dict[str, object] = {
            "classifier_provider": self.classifier_provider,
            "classifier_model": self.classifier_model,
            "reasoning_provider": self.reasoning_provider,
            "reasoning_model": self.reasoning_model,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "vector_store": self.vector_store,
            "vector_collection_prefix": self.vector_collection_prefix,
            "chromadb_persist_path": self.chromadb_persist_path,
            "pinecone_index_name": self.pinecone_index_name,
            "pinecone_cloud": self.pinecone_cloud,
            "pinecone_region": self.pinecone_region,
            "pgvector_schema": self.pgvector_schema,
            "ollama_base_url": self.ollama_base_url,
            "database_url": self.database_url,
        }
        optional_values = {
            "anthropic_api_key": self.anthropic_api_key,
            "openai_api_key": self.openai_api_key,
            "groq_api_key": self.groq_api_key,
            "together_api_key": self.together_api_key,
            "google_api_key": self.google_api_key,
            "qdrant_url": self.qdrant_url,
            "qdrant_api_key_ro": self.qdrant_api_key_ro,
            "pinecone_api_key": self.pinecone_api_key,
            "pinecone_index_host": self.pinecone_index_host,
            "pgvector_dsn": self.pgvector_dsn,
        }
        values.update({key: value for key, value in optional_values.items() if value is not None})
        return ChainConfig(**cast(Any, values))


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Return the singleton AppConfig (cached after first call)."""
    return AppConfig()
