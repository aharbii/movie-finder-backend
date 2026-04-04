"""User models safe to expose across application layers."""

from __future__ import annotations

from pydantic import BaseModel


class UserOut(BaseModel):
    """Authenticated user data safe to inject into route handlers."""

    id: str
    email: str
