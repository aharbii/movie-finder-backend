"""Tests for auth middleware (unit) and auth router (integration)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

# ---------------------------------------------------------------------------
# Unit — password hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self) -> None:
        from app.auth.middleware import hash_password

        assert hash_password("secret") != "secret"

    def test_verify_correct_password(self) -> None:
        from app.auth.middleware import hash_password, verify_password

        h = hash_password("mysecret")
        assert verify_password("mysecret", h) is True

    def test_verify_wrong_password(self) -> None:
        from app.auth.middleware import hash_password, verify_password

        h = hash_password("mysecret")
        assert verify_password("wrong", h) is False

    def test_two_hashes_of_same_password_differ(self) -> None:
        """bcrypt uses a random salt — identical inputs should produce different hashes."""
        from app.auth.middleware import hash_password

        assert hash_password("same") != hash_password("same")


# ---------------------------------------------------------------------------
# Unit — JWT creation and verification
# ---------------------------------------------------------------------------


class TestJWT:
    def test_access_token_round_trip(self) -> None:
        from app.auth.middleware import create_access_token, verify_token

        token = create_access_token("user-123")
        data = verify_token(token)
        assert data.user_id == "user-123"
        assert data.token_type == "access"

    def test_refresh_token_round_trip(self) -> None:
        from app.auth.middleware import create_refresh_token, verify_token

        token = create_refresh_token("user-456")
        data = verify_token(token)
        assert data.user_id == "user-456"
        assert data.token_type == "refresh"
        assert data.jti is not None
        assert data.expires_at is not None

    def test_invalid_token_raises_401(self) -> None:
        from app.auth.middleware import verify_token

        with pytest.raises(HTTPException) as exc_info:
            verify_token("not.a.valid.token")
        assert exc_info.value.status_code == 401

    def test_tampered_token_raises_401(self) -> None:
        from app.auth.middleware import create_access_token, verify_token

        token = create_access_token("user-789") + "tampered"
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Integration — POST /auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_successful_registration_returns_201(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "password123",  # pragma: allowlist secret
            },
        )
        assert resp.status_code == 201

    async def test_successful_registration_returns_token_pair(
        self, client: httpx.AsyncClient
    ) -> None:
        resp = await client.post(
            "/auth/register",
            json={
                "email": "bob@example.com",
                "password": "password123",  # pragma: allowlist secret
            },
        )
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    async def test_duplicate_email_returns_409(self, client: httpx.AsyncClient) -> None:
        payload = {
            "email": "dup@example.com",
            "password": "password123",  # pragma: allowlist secret
        }
        await client.post("/auth/register", json=payload)
        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_short_password_returns_422(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/auth/register",
            json={"email": "short@example.com", "password": "abc"},  # pragma: allowlist secret
        )
        assert resp.status_code == 422

    async def test_invalid_email_returns_422(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "password123"},  # pragma: allowlist secret
        )
        assert resp.status_code == 422

    async def test_access_token_is_valid_jwt(self, client: httpx.AsyncClient) -> None:
        from app.auth.middleware import verify_token

        resp = await client.post(
            "/auth/register",
            json={
                "email": "check@example.com",
                "password": "password123",  # pragma: allowlist secret
            },
        )
        token_data = verify_token(resp.json()["access_token"])
        assert token_data.token_type == "access"


# ---------------------------------------------------------------------------
# Integration — POST /auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_correct_credentials_returns_200(
        self, client: httpx.AsyncClient, registered_user: tuple[str, str, str]
    ) -> None:
        email, password, _ = registered_user
        resp = await client.post("/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200

    async def test_correct_credentials_returns_token_pair(
        self, client: httpx.AsyncClient, registered_user: tuple[str, str, str]
    ) -> None:
        email, password, _ = registered_user
        resp = await client.post("/auth/login", json={"email": email, "password": password})
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    async def test_wrong_password_returns_401(
        self, client: httpx.AsyncClient, registered_user: tuple[str, str, str]
    ) -> None:
        email, _, _ = registered_user
        resp = await client.post(
            "/auth/login",
            json={"email": email, "password": "wrongpassword"},  # pragma: allowlist secret
        )
        assert resp.status_code == 401

    async def test_unknown_email_returns_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/auth/login",
            json={
                "email": "ghost@example.com",
                "password": "password123",  # pragma: allowlist secret
            },
        )
        assert resp.status_code == 401

    async def test_rate_limit_returns_429_and_retry_after(
        self,
        client: httpx.AsyncClient,
        registered_user: tuple[str, str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.config import get_config

        email, password, _ = registered_user
        monkeypatch.setenv("AUTH_RATE_LIMIT", "1/minute")
        get_config.cache_clear()

        first = await client.post("/auth/login", json={"email": email, "password": password})
        second = await client.post("/auth/login", json={"email": email, "password": password})
        assert first.status_code == 200
        assert second.status_code == 429
        assert "Retry-After" in second.headers


# ---------------------------------------------------------------------------
# Integration — POST /auth/refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    async def test_valid_refresh_token_returns_new_pair(
        self, client: httpx.AsyncClient, registered_user: tuple[str, str, str]
    ) -> None:
        email, password, _ = registered_user
        login = await client.post("/auth/login", json={"email": email, "password": password})
        refresh_token = login.json()["refresh_token"]

        resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    async def test_access_token_rejected_as_refresh(
        self, client: httpx.AsyncClient, registered_user: tuple[str, str, str]
    ) -> None:
        _, _, access_token = registered_user
        resp = await client.post("/auth/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401

    async def test_invalid_token_rejected(self, client: httpx.AsyncClient) -> None:
        resp = await client.post("/auth/refresh", json={"refresh_token": "garbage.token.value"})
        assert resp.status_code == 401

    async def test_revoked_refresh_token_rejected(
        self, client: httpx.AsyncClient, registered_user: tuple[str, str, str]
    ) -> None:
        email, password, _ = registered_user
        login = await client.post("/auth/login", json={"email": email, "password": password})
        refresh_token = login.json()["refresh_token"]

        logout = await client.post("/auth/logout", json={"refresh_token": refresh_token})
        assert logout.status_code == 204

        resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401


class TestLogout:
    async def test_valid_refresh_token_returns_204(
        self, client: httpx.AsyncClient, registered_user: tuple[str, str, str]
    ) -> None:
        email, password, _ = registered_user
        login = await client.post("/auth/login", json={"email": email, "password": password})
        refresh_token = login.json()["refresh_token"]

        resp = await client.post("/auth/logout", json={"refresh_token": refresh_token})
        assert resp.status_code == 204

    async def test_access_token_rejected_as_logout_token(
        self, client: httpx.AsyncClient, registered_user: tuple[str, str, str]
    ) -> None:
        _, _, access_token = registered_user
        resp = await client.post("/auth/logout", json={"refresh_token": access_token})
        assert resp.status_code == 401


class TestCurrentUserDependency:
    async def test_returns_user_out_without_hashed_password(self) -> None:
        from app.dependencies import get_current_user

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="unused",
        )
        store = AsyncMock()
        store.get_user_by_id.return_value = type(
            "UserRecord",
            (),
            {
                "id": "user-1",
                "email": "user@example.com",
                "hashed_password": "secret-hash",  # pragma: allowlist secret
            },
        )()

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "app.dependencies.verify_token",
                lambda token: type(
                    "TokenData", (), {"user_id": "user-1", "token_type": "access"}
                )(),
            )
            current_user = await get_current_user(credentials=credentials, store=store)

        assert current_user.id == "user-1"
        assert current_user.email == "user@example.com"
        assert not hasattr(current_user, "hashed_password")
