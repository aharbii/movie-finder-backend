"""Authentication router — register / login / refresh."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth.middleware import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.auth.models import RefreshRequest, Token, UserCreate, UserLogin
from app.dependencies import get_store
from app.limiting import auth_rate_limit, limiter
from app.session.store import SessionStore

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user_id: str) -> Token:
    """Create a fresh access/refresh token pair for a user."""
    return Token(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    store: Annotated[SessionStore, Depends(get_store)],
) -> Token:
    """Create a new account and return a JWT pair."""
    if await store.get_user_by_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = await store.create_user(body.email, hash_password(body.password))
    return _issue_tokens(user.id)


@router.post("/login", response_model=Token)
@router.post("/token", response_model=Token, include_in_schema=False)
@limiter.limit(auth_rate_limit)  # type: ignore[untyped-decorator]
async def login(
    request: Request,
    body: UserLogin,
    store: Annotated[SessionStore, Depends(get_store)],
) -> Token:
    """Authenticate with email + password and return a JWT pair."""
    user = await store.get_user_by_email(body.email)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return _issue_tokens(user.id)


@router.post("/refresh", response_model=Token)
async def refresh(
    body: RefreshRequest,
    store: Annotated[SessionStore, Depends(get_store)],
) -> Token:
    """Exchange a valid refresh token for a new JWT pair."""
    token_data = verify_token(body.refresh_token)
    if token_data.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected a refresh token",
        )
    if token_data.jti is None or token_data.expires_at is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing required claims",
        )
    if await store.is_refresh_token_revoked(token_data.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )
    user = await store.get_user_by_id(token_data.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return _issue_tokens(user.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    store: Annotated[SessionStore, Depends(get_store)],
) -> Response:
    """Revoke a refresh token by blocklisting its JTI until expiry."""
    token_data = verify_token(body.refresh_token)
    if (
        token_data.token_type != "refresh"
        or token_data.jti is None
        or token_data.expires_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected a refresh token",
        )
    await store.revoke_refresh_token(token_data.jti, token_data.expires_at)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
