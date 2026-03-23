"""Chat router — streaming conversation endpoint and history retrieval."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from app.auth.models import UserInDB
from app.dependencies import get_current_user, get_graph, get_store
from app.session.store import SessionStore

router = APIRouter(prefix="/chat", tags=["chat"])

# Nodes whose LLM output is user-facing and should be streamed token-by-token.
_USER_FACING_NODES = frozenset({"presentation", "qa_agent", "dead_end", "refinement"})


def _message_text(msg: Any) -> str:
    """Return the plain text of a LangChain message, handling both str and
    Anthropic list-of-content-blocks formats.

    Anthropic models occasionally return ``content`` as a list of typed blocks,
    e.g. ``[{"type": "text", "text": "Great choice!..."}]``, instead of a
    plain string.  ``isinstance(content, str)`` would silently fail in that
    case and produce an empty reply.
    """
    if not isinstance(msg, AIMessage):
        return ""
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
            if not isinstance(block, dict) or block.get("type") == "text"
        )
    return ""


class ChatRequest(BaseModel):
    session_id: str
    message: str


# ---------------------------------------------------------------------------
# SSE stream generator
# ---------------------------------------------------------------------------


async def _stream_reply(
    graph: Any,
    session_id: str,
    message: str,
    store: SessionStore,
) -> AsyncGenerator[str, None]:  # noqa: UP043
    """Yield SSE-formatted lines for the duration of a single graph invocation.

    Events emitted:
      {"type": "token",  "content": "<chunk>"}   — one per streamed LLM token
      {"type": "done",   "session_id": ..., "reply": ..., "phase": ...,
       ["candidates": [...]], ["confirmed_movie": {...}]}
    """
    config: dict[str, Any] = {"configurable": {"thread_id": session_id}}
    reply_chunks: list[str] = []
    final_output: dict[str, Any] = {}

    async for event in graph.astream_events(
        {"messages": [HumanMessage(content=message)]},
        config=config,
        version="v2",
    ):
        kind: str = event.get("event", "")

        # Stream tokens only from user-facing nodes so internal classifier /
        # refinement structured outputs don't reach the client.
        if kind == "on_chat_model_stream":
            node = event.get("metadata", {}).get("langgraph_node", "")
            if node in _USER_FACING_NODES:
                chunk = event["data"]["chunk"]
                token: str = _message_text(chunk)
                if token:
                    reply_chunks.append(token)
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        elif kind == "on_chain_end" and event.get("name") == "LangGraph":
            output = event.get("data", {}).get("output", {})
            if isinstance(output, dict):
                final_output = output

    # Build the canonical reply text ----------------------------------------
    if reply_chunks:
        reply_text = "".join(reply_chunks)
    else:
        # Fallback: pull last AIMessage from the graph output.
        # Uses _message_text() so Anthropic list-of-blocks content is handled
        # correctly — the qa_agent node uses ainvoke (no token streaming), so
        # this path is the only source of its reply text.
        msgs: list[Any] = final_output.get("messages", [])
        last_ai = next((m for m in reversed(msgs) if isinstance(m, AIMessage)), None)
        reply_text = _message_text(last_ai) if last_ai else ""

    phase: str = final_output.get("phase", "discovery")

    # Persist to our store (independent of the LangGraph checkpointer) -------
    await store.append_message(session_id, "user", message)
    if reply_text:
        await store.append_message(session_id, "assistant", reply_text)
    await store.update_session_phase(session_id, phase)

    # Final done event --------------------------------------------------------
    result: dict[str, Any] = {
        "type": "done",
        "session_id": session_id,
        "reply": reply_text,
        "phase": phase,
    }
    if phase == "confirmation" and final_output.get("enriched_movies"):
        result["candidates"] = final_output["enriched_movies"]
    if phase == "qa" and final_output.get("confirmed_movie_data"):
        result["confirmed_movie"] = final_output["confirmed_movie_data"]

    yield f"data: {json.dumps(result)}\n\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("")
async def chat(
    body: ChatRequest,
    current_user: Annotated[UserInDB, Depends(get_current_user)],
    store: Annotated[SessionStore, Depends(get_store)],
    graph: Annotated[Any, Depends(get_graph)],
) -> StreamingResponse:
    """Send a message and receive an SSE stream of AI reply tokens + a final result event."""
    # Resolve session — create it if this is the first message in a new thread.
    session = await store.get_or_create_session(body.session_id, current_user.id)
    if session["user_id"] != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session not found")

    return StreamingResponse(
        _stream_reply(graph, body.session_id, body.message, store),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{session_id}/history")
async def get_history(
    session_id: str,
    current_user: Annotated[UserInDB, Depends(get_current_user)],
    store: Annotated[SessionStore, Depends(get_store)],
) -> dict[str, Any]:
    """Return the full message history for a session owned by the current user."""
    session = await store.get_session(session_id)
    if session is None or session["user_id"] != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    messages = await store.get_messages(session_id)
    return {
        "session_id": session_id,
        "phase": session["phase"],
        "messages": messages,
    }
