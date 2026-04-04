"""Shared rate-limiting configuration and key functions."""

from __future__ import annotations

from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth.middleware import verify_token
from app.config import get_config


def _global_rate_limit() -> str:
    """Return the configured global fallback rate limit."""
    return get_config().global_rate_limit


def auth_rate_limit() -> str:
    """Return the configured login/token route rate limit."""
    return get_config().auth_rate_limit


def chat_rate_limit() -> str:
    """Return the configured chat route rate limit."""
    return get_config().chat_rate_limit


def chat_limit_key(request: Request) -> str:
    """Rate-limit chat by authenticated user, with IP fallback."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            token_data = verify_token(auth_header.removeprefix("Bearer ").strip())
            if token_data.token_type == "access":
                return f"user:{token_data.user_id}"
        except HTTPException:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=get_remote_address, default_limits=[_global_rate_limit])
