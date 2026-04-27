"""Shared FastAPI dependencies.

Singletons (graph, store) are set by the lifespan handler in main.py and
then injected into route handlers via Depends().
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.middleware import verify_token
from app.config import AppConfig
from app.models.user import UserOut
from app.session.store import SessionStore
from chain.config import configure_runtime_config

if TYPE_CHECKING:
    from langgraph.graph.graph import CompiledGraph

_bearer = HTTPBearer()

# ---------------------------------------------------------------------------
# Graph singleton — set once in lifespan, injected via get_graph()
# ---------------------------------------------------------------------------

_graph: CompiledGraph | None = None


def set_graph(graph: Any) -> None:  # noqa: ANN401
    """Store the compiled graph singleton for later dependency injection."""
    global _graph
    _graph = graph


def get_graph() -> Any:  # noqa: ANN401
    """Return the compiled graph singleton."""
    if _graph is None:
        raise RuntimeError("Graph not initialized — lifespan not started")
    return _graph


def configure_chain_runtime(config: AppConfig) -> None:
    """Pass validated backend provider settings to the chain package."""
    configure_runtime_config(config.to_chain_config())


# ---------------------------------------------------------------------------
# Store singleton — set once in lifespan, injected via get_store()
# ---------------------------------------------------------------------------

_store: SessionStore | None = None


def set_store(store: SessionStore) -> None:
    """Store the session repository singleton for later dependency injection."""
    global _store
    _store = store


def get_store() -> SessionStore:
    """Return the configured session repository singleton."""
    if _store is None:
        raise RuntimeError("SessionStore not initialized — lifespan not started")
    return _store


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    store: Annotated[SessionStore, Depends(get_store)],
) -> UserOut:
    """Resolve the authenticated user while keeping password hashes internal."""
    token_data = verify_token(credentials.credentials)
    if token_data.token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected an access token",
        )
    user = await store.get_user_by_id(token_data.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return UserOut(id=user.id, email=user.email)
