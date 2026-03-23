"""Shared FastAPI dependencies.

Singletons (graph, store) are set by the lifespan handler in main.py and
then injected into route handlers via Depends().
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.middleware import verify_token
from app.auth.models import UserInDB
from app.session.store import SessionStore

if TYPE_CHECKING:
    from langgraph.graph.graph import CompiledGraph

_bearer = HTTPBearer()

# ---------------------------------------------------------------------------
# Graph singleton — set once in lifespan, injected via get_graph()
# ---------------------------------------------------------------------------

_graph: CompiledGraph | None = None


def set_graph(graph: Any) -> None:  # noqa: ANN401
    global _graph
    _graph = graph


def get_graph() -> Any:  # noqa: ANN401
    if _graph is None:
        raise RuntimeError("Graph not initialized — lifespan not started")
    return _graph


# ---------------------------------------------------------------------------
# Store singleton — set once in lifespan, injected via get_store()
# ---------------------------------------------------------------------------

_store: SessionStore | None = None


def set_store(store: SessionStore) -> None:
    global _store
    _store = store


def get_store() -> SessionStore:
    if _store is None:
        raise RuntimeError("SessionStore not initialized — lifespan not started")
    return _store


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    store: Annotated[SessionStore, Depends(get_store)],
) -> UserInDB:
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
    return user
