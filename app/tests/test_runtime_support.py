"""Focused coverage for runtime helpers outside the HTTP happy paths."""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from langchain_core.messages import AIMessage, HumanMessage
from starlette.requests import Request


def _request(headers: dict[str, str] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/chat",
            "headers": [
                (key.lower().encode("latin-1"), value.encode("latin-1"))
                for key, value in (headers or {}).items()
            ],
            "client": ("203.0.113.10", 43210),
        }
    )


class TestDependencySingletons:
    def test_graph_singleton_guard_and_setter(self) -> None:
        from app import dependencies

        previous = dependencies._graph
        dependencies._graph = None
        try:
            with pytest.raises(RuntimeError, match="Graph not initialized"):
                dependencies.get_graph()
            graph = object()
            dependencies.set_graph(graph)
            assert dependencies.get_graph() is graph
        finally:
            dependencies._graph = previous

    def test_store_singleton_guard_and_setter(self) -> None:
        from app import dependencies

        previous = dependencies._store
        dependencies._store = None
        try:
            with pytest.raises(RuntimeError, match="SessionStore not initialized"):
                dependencies.get_store()
            store = object()
            dependencies.set_store(store)  # type: ignore[arg-type]
            assert dependencies.get_store() is store
        finally:
            dependencies._store = previous

    def test_configure_chain_runtime_passes_chain_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.config import AppConfig
        from app.dependencies import configure_chain_runtime

        captured: dict[str, Any] = {}

        monkeypatch.setattr(
            "app.dependencies.configure_runtime_config",
            lambda chain_config: captured.setdefault("config", chain_config),
        )

        config = AppConfig(
            app_secret_key="test-secret-key",
            database_url="postgresql://user@postgres:5432/movie_finder",
            classifier_provider="ollama",
            classifier_model="llama3.1:8b",
        )

        configure_chain_runtime(config)

        assert captured["config"].classifier_provider == "ollama"
        assert captured["config"].classifier_model == "llama3.1:8b"


class TestCurrentUserDependencyErrors:
    async def test_rejects_refresh_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.dependencies import get_current_user

        monkeypatch.setattr(
            "app.dependencies.verify_token",
            lambda token: SimpleNamespace(user_id="user-1", token_type="refresh"),
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
                store=AsyncMock(),
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Expected an access token"

    async def test_rejects_missing_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.dependencies import get_current_user

        store = AsyncMock()
        store.get_user_by_id.return_value = None
        monkeypatch.setattr(
            "app.dependencies.verify_token",
            lambda token: SimpleNamespace(user_id="missing", token_type="access"),
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
                store=store,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "User not found"


class TestRateLimitHelpers:
    def test_chat_limit_key_uses_user_id_for_valid_access_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.limiting import chat_limit_key

        monkeypatch.setattr(
            "app.limiting.verify_token",
            lambda token: SimpleNamespace(user_id="user-1", token_type="access"),
        )

        assert chat_limit_key(_request({"Authorization": "Bearer token"})) == "user:user-1"

    def test_chat_limit_key_falls_back_to_ip_for_refresh_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.limiting import chat_limit_key

        monkeypatch.setattr(
            "app.limiting.verify_token",
            lambda token: SimpleNamespace(user_id="user-1", token_type="refresh"),
        )

        assert chat_limit_key(_request({"Authorization": "Bearer token"})) == "ip:203.0.113.10"

    def test_chat_limit_key_falls_back_to_ip_for_invalid_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.limiting import chat_limit_key

        def _raise(_: str) -> None:
            raise HTTPException(status_code=401, detail="invalid")

        monkeypatch.setattr("app.limiting.verify_token", _raise)

        assert chat_limit_key(_request({"Authorization": "Bearer bad-token"})) == "ip:203.0.113.10"

    def test_chat_limit_key_falls_back_to_ip_without_bearer_header(self) -> None:
        from app.limiting import chat_limit_key

        assert chat_limit_key(_request({"Authorization": "Token value"})) == "ip:203.0.113.10"


class TestLoggingConfig:
    @pytest.fixture(autouse=True)
    def _reset_loggers(self) -> Iterator[None]:
        namespaces = ("app", "chain", "imdbapi", "rag")
        previous = {
            name: (
                list(logging.getLogger(name).handlers),
                logging.getLogger(name).propagate,
                logging.getLogger(name).level,
            )
            for name in namespaces
        }
        for name in namespaces:
            logger = logging.getLogger(name)
            logger.handlers.clear()
            logger.propagate = True
        yield
        for name in namespaces:
            logger = logging.getLogger(name)
            logger.handlers.clear()
            logger.handlers.extend(previous[name][0])
            logger.propagate = previous[name][1]
            logger.setLevel(previous[name][2])

    def test_configure_logging_json_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.logging_config import configure_logging

        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("LOG_FORMAT", "json")

        configure_logging()

        logger = logging.getLogger("app")
        record = logger.makeRecord(
            name="app.test",
            level=logging.INFO,
            fn=__file__,
            lno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
            func=None,
        )
        formatter = logger.handlers[0].formatter
        assert formatter is not None
        payload = json.loads(formatter.format(record))

        assert payload["level"] == "INFO"
        assert payload["logger"] == "app.test"
        assert payload["message"] == "hello world"
        assert logging.getLogger("httpx").level == logging.DEBUG
        assert logging.getLogger("uvicorn.error").level == logging.WARNING

    def test_configure_logging_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.logging_config import configure_logging

        monkeypatch.setenv("LOG_LEVEL", "NOT_A_LEVEL")

        configure_logging()
        first_handlers = list(logging.getLogger("app").handlers)
        configure_logging()

        assert logging.getLogger("app").handlers == first_handlers
        assert logging.getLogger("app").level == logging.INFO

    def test_json_formatter_includes_exception(self) -> None:
        from app.logging_config import _JsonFormatter

        try:
            raise ValueError("bad log")
        except ValueError:
            record = logging.LogRecord(
                name="app.test",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="failed",
                args=(),
                exc_info=sys.exc_info(),
                func=None,
                sinfo=None,
            )

        payload = json.loads(_JsonFormatter().format(record))

        assert payload["message"] == "failed"
        assert "ValueError: bad log" in payload["exception"]


def test_retry_after_value_uses_limit_expiry() -> None:
    from slowapi.errors import RateLimitExceeded

    from app.main import _retry_after_value

    exc = cast(
        RateLimitExceeded,
        SimpleNamespace(limit=SimpleNamespace(get_expiry=lambda: 12.9)),
    )

    assert _retry_after_value(exc) == "12"


async def test_rate_limit_handler_handles_plain_exceptions() -> None:
    from app.main import rate_limit_exceeded_handler

    response = await rate_limit_exceeded_handler(_request(), Exception("boom"))

    assert response.status_code == 429
    assert "Retry-After" not in response.headers


async def test_close_checkpointer_accepts_none() -> None:
    from app.main import _close_checkpointer

    await _close_checkpointer(None)


class TestMessageText:
    def test_returns_empty_for_non_ai_message(self) -> None:
        from app.routers.chat import _message_text

        assert _message_text(HumanMessage(content="hello")) == ""

    def test_flattens_anthropic_text_blocks(self) -> None:
        from app.routers.chat import _message_text

        message = AIMessage(
            content=[
                {"type": "text", "text": "First "},
                {"type": "tool_use", "text": "skip"},
                {"type": "text", "text": "second"},
                " tail",
            ]
        )

        assert _message_text(message) == "First second tail"

    def test_returns_empty_for_unknown_content_shape(self) -> None:
        from app.routers.chat import _message_text

        message = AIMessage(content=[])
        message.content = object()  # type: ignore[assignment]

        assert _message_text(message) == ""


async def test_stream_reply_filters_non_user_tokens_and_empty_output() -> None:
    from app.routers.chat import _stream_reply

    class Graph:
        async def astream_events(self, *args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            yield {
                "event": "on_chat_model_stream",
                "metadata": {"langgraph_node": "classifier"},
                "data": {"chunk": AIMessage(content="internal")},
            }
            yield {
                "event": "on_chat_model_stream",
                "metadata": {"langgraph_node": "presentation"},
                "data": {"chunk": HumanMessage(content="not ai")},
            }
            yield {
                "event": "on_chain_end",
                "name": "OtherGraph",
                "data": {"output": {"phase": "qa"}},
            }
            yield {
                "event": "on_chain_end",
                "name": "LangGraph",
                "data": {"output": ["not", "a", "dict"]},
            }

    store = AsyncMock()

    events = [
        json.loads(line.removeprefix("data: "))
        async for line in _stream_reply(Graph(), "session-1", "hello", store)
        if line.startswith("data: ")
    ]

    assert events == [
        {
            "type": "done",
            "session_id": "session-1",
            "reply": "",
            "phase": "discovery",
        }
    ]
    store.append_message.assert_awaited_once_with("session-1", "user", "hello")
    store.update_session_phase.assert_awaited_once_with("session-1", "discovery")


class TestAuthRouterClaimErrors:
    async def test_refresh_rejects_missing_refresh_claims(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.routers.auth import refresh

        monkeypatch.setattr(
            "app.routers.auth.verify_token",
            lambda token: SimpleNamespace(
                token_type="refresh",
                user_id="user-1",
                jti=None,
                expires_at=None,
            ),
        )

        with pytest.raises(HTTPException) as exc_info:
            await refresh(SimpleNamespace(refresh_token="token"), AsyncMock())  # type: ignore[arg-type]

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Refresh token missing required claims"

    async def test_refresh_rejects_missing_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.routers.auth import refresh

        store = AsyncMock()
        store.is_refresh_token_revoked.return_value = False
        store.get_user_by_id.return_value = None
        monkeypatch.setattr(
            "app.routers.auth.verify_token",
            lambda token: SimpleNamespace(
                token_type="refresh",
                user_id="missing",
                jti="jti-1",
                expires_at=time.time(),
            ),
        )

        with pytest.raises(HTTPException) as exc_info:
            await refresh(SimpleNamespace(refresh_token="token"), store)  # type: ignore[arg-type]

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "User not found"

    async def test_logout_rejects_missing_refresh_claims(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.routers.auth import logout

        monkeypatch.setattr(
            "app.routers.auth.verify_token",
            lambda token: SimpleNamespace(
                token_type="refresh",
                user_id="user-1",
                jti=None,
                expires_at=None,
            ),
        )

        with pytest.raises(HTTPException) as exc_info:
            await logout(SimpleNamespace(refresh_token="token"), AsyncMock())  # type: ignore[arg-type]

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Expected a refresh token"
