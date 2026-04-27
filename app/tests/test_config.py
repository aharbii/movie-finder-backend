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


def test_app_config_rejects_invalid_provider() -> None:
    with pytest.raises(ValidationError):
        _make_config(classifier_provider="invalid")


def test_app_config_rejects_blank_vector_collection_prefix() -> None:
    with pytest.raises(ValidationError, match="VECTOR_COLLECTION_PREFIX"):
        _make_config(vector_collection_prefix=" ")
