"""JWT operations and password hashing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.auth.models import TokenData
from app.config import get_config

ALGORITHM = "HS256"


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return str(bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return bool(bcrypt.checkpw(plain.encode(), hashed.encode()))


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


def create_access_token(user_id: str) -> str:
    """Create a signed access token for a user."""
    cfg = get_config()
    expire = datetime.now(UTC) + timedelta(minutes=cfg.access_token_expire_minutes)
    payload = {"sub": user_id, "type": "access", "exp": expire}
    return jwt.encode(payload, cfg.app_secret_key, algorithm=ALGORITHM)  # type: ignore[no-any-return]


def create_refresh_token(user_id: str) -> str:
    """Create a signed refresh token with a unique revocation ID."""
    cfg = get_config()
    expire = datetime.now(UTC) + timedelta(days=cfg.refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, cfg.app_secret_key, algorithm=ALGORITHM)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def verify_token(token: str) -> TokenData:
    """Decode and validate a JWT, returning normalized token metadata."""
    cfg = get_config()
    try:
        payload = jwt.decode(token, cfg.app_secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise _credentials_exc from None
    user_id: str = payload.get("sub", "")
    token_type: str = payload.get("type", "")
    jti = payload.get("jti")
    expires_at = payload.get("exp")
    if not user_id or not token_type:
        raise _credentials_exc
    parsed_expiry: datetime | None = None
    if isinstance(expires_at, (int, float)):
        parsed_expiry = datetime.fromtimestamp(expires_at, tz=UTC)
    return TokenData(
        user_id=user_id,
        token_type=token_type,
        jti=jti if isinstance(jti, str) else None,
        expires_at=parsed_expiry,
    )
