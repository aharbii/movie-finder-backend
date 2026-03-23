"""JWT operations and password hashing."""

from __future__ import annotations

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
    return str(bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())


def verify_password(plain: str, hashed: str) -> bool:
    return bool(bcrypt.checkpw(plain.encode(), hashed.encode()))


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


def create_access_token(user_id: str) -> str:
    cfg = get_config()
    expire = datetime.now(UTC) + timedelta(minutes=cfg.access_token_expire_minutes)
    payload = {"sub": user_id, "type": "access", "exp": expire}
    return jwt.encode(payload, cfg.app_secret_key, algorithm=ALGORITHM)  # type: ignore[no-any-return]


def create_refresh_token(user_id: str) -> str:
    cfg = get_config()
    expire = datetime.now(UTC) + timedelta(days=cfg.refresh_token_expire_days)
    payload = {"sub": user_id, "type": "refresh", "exp": expire}
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
    cfg = get_config()
    try:
        payload = jwt.decode(token, cfg.app_secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise _credentials_exc from None
    user_id: str = payload.get("sub", "")
    token_type: str = payload.get("type", "")
    if not user_id or not token_type:
        raise _credentials_exc
    return TokenData(user_id=user_id, token_type=token_type)
