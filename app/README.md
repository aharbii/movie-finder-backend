# app/ — FastAPI Application (Placeholder)

This directory will contain the FastAPI application that wraps the AI chain and exposes it to end users.

## Planned features

- **User authentication** — JWT-based auth (register / login / refresh)
- **Chat endpoint** — `POST /chat` — stateful multi-turn conversation with the AI chain
- **Session management** — persistent conversation threads per user
- **Rate limiting** — per-user request throttling

## Planned structure

```
app/
├── pyproject.toml          # uv workspace member — added to backend/pyproject.toml
└── src/app/
    ├── main.py             # FastAPI() + lifespan + /health
    ├── routers/
    │   ├── auth.py         # POST /auth/register, /auth/login, /auth/refresh
    │   └── chat.py         # POST /chat, GET /chat/{session_id}/history
    ├── auth/
    │   ├── middleware.py   # JWT validation middleware
    │   └── models.py       # User, Token Pydantic models
    ├── dependencies.py     # Shared FastAPI dependencies (get_current_user, etc.)
    └── config.py           # AppConfig (Pydantic Settings)
```

## Integration with chain

The app imports `chain.compile_graph` and wraps it in an async streaming endpoint:

```python
from chain import compile_graph

graph = compile_graph()
# graph.astream(input, config={"configurable": {"thread_id": session_id}})
```

## Setup (once implemented)

```bash
cd backend/
cp .env.example .env && $EDITOR .env
uv sync --group dev          # installs app + chain + imdbapi in workspace
uv run fastapi dev app/src/app/main.py
```

## Environment variables

See the `# App` section in [../.env.example](../.env.example).
