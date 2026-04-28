"""Tests for backend application configuration."""

from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.config import AppConfig


def _make_config(**overrides: object) -> AppConfig:
    settings: dict[str, object] = {
        "app_secret_key": "test-secret-key",
        "database_url": "postgresql://user:pass@postgres:5432/movie_finder",
    }
    settings.update(overrides)
    return AppConfig(**cast(Any, settings))


def test_to_chain_config_uses_targeted_provider_settings() -> None:
    config = _make_config(
        classifier_provider="ollama",
        classifier_model="llama3.1:8b",
        reasoning_provider="ollama",
        reasoning_model="llama3.1:8b",
        embedding_provider="ollama",
        embedding_model="nomic-embed-text",
        embedding_dimension=768,
        vector_store="qdrant",
        vector_collection_prefix="movies",
        ollama_base_url="http://ollama:11434/",
    )

    chain_config = config.to_chain_config()

    assert chain_config.classifier_provider == "ollama"
    assert chain_config.classifier_model == "llama3.1:8b"
    assert chain_config.reasoning_provider == "ollama"
    assert chain_config.reasoning_model == "llama3.1:8b"
    assert chain_config.embedding_provider == "ollama"
    assert chain_config.embedding_model == "nomic-embed-text"
    assert chain_config.embedding_dimension == 768
    assert chain_config.vector_collection_name == "movies_nomic_embed_text_768"
    assert chain_config.ollama_base_url == "http://ollama:11434"


def test_to_chain_config_allows_node_specific_models() -> None:
    config = _make_config(
        classifier_provider="openai",
        classifier_model="gpt-4.1-mini",
        reasoning_provider="groq",
        reasoning_model="llama-3.3-70b-versatile",
    )

    chain_config = config.to_chain_config()

    assert chain_config.classifier_provider == "openai"
    assert chain_config.classifier_model == "gpt-4.1-mini"
    assert chain_config.reasoning_provider == "groq"
    assert chain_config.reasoning_model == "llama-3.3-70b-versatile"


def test_to_chain_config_includes_optional_provider_settings() -> None:
    config = _make_config(
        anthropic_api_key="anthropic-key",
        openai_api_key="openai-key",
        groq_api_key="groq-key",
        together_api_key="together-key",
        google_api_key="google-key",
        qdrant_url="https://qdrant.example.com/",
        qdrant_api_key_ro="qdrant-read-key",
        pinecone_api_key="pinecone-key",
        pinecone_index_host="https://pinecone.example.com/",
        pgvector_dsn="postgresql://user:pass@pgvector:5432/vector_db",
    )

    chain_config = config.to_chain_config()

    assert chain_config.anthropic_api_key == "anthropic-key"
    assert chain_config.openai_api_key == "openai-key"
    assert chain_config.groq_api_key == "groq-key"
    assert chain_config.together_api_key == "together-key"
    assert chain_config.google_api_key == "google-key"
    assert chain_config.qdrant_url == "https://qdrant.example.com"
    assert chain_config.qdrant_api_key_ro == "qdrant-read-key"
    assert chain_config.pinecone_api_key == "pinecone-key"
    assert chain_config.pinecone_index_host == "https://pinecone.example.com"
    assert chain_config.pgvector_dsn == "postgresql://user:pass@pgvector:5432/vector_db"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (
            '["https://app.example.com", "http://localhost:4200"]',
            ["https://app.example.com", "http://localhost:4200"],
        ),
        (
            "https://app.example.com, http://localhost:4200, ",
            ["https://app.example.com", "http://localhost:4200"],
        ),
        ("   ", []),
        (["https://already.example.com"], ["https://already.example.com"]),
    ],
)
def test_cors_origins_are_coerced(raw_value: object, expected: list[str]) -> None:
    config = _make_config(cors_origins=raw_value)

    assert config.cors_origins == expected


def test_optional_provider_urls_accept_none() -> None:
    config = _make_config(qdrant_url=None, pinecone_index_host=None)

    assert config.qdrant_url is None
    assert config.pinecone_index_host is None


def test_app_config_rejects_invalid_provider() -> None:
    with pytest.raises(ValidationError):
        _make_config(classifier_provider="invalid")


def test_app_config_rejects_blank_vector_collection_prefix() -> None:
    with pytest.raises(ValidationError, match="VECTOR_COLLECTION_PREFIX"):
        _make_config(vector_collection_prefix=" ")
