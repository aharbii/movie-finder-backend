# app/ — FastAPI Application

FastAPI application that wraps the AI chain and exposes it to end users via a REST API with JWT authentication, streaming chat, and persistent session management.

---

## Implemented features

- **User authentication** — JWT register / login / refresh / logout (`/auth/*`)
- **Streaming chat** — `POST /chat` — multi-turn conversation with the AI chain, streamed via SSE
- **Session management** — persistent conversation threads per user stored in PostgreSQL
- **Session history** — `GET /chat/{session_id}/history` — full message history
- **Session list** — `GET /chat/sessions` — all sessions for the current user with metadata
- **Session delete** — `DELETE /chat/{session_id}` — remove a session and its messages
- **Confirmed movie** — `qa` phase persists the confirmed movie metadata to the session

---

## Structure

```
app/
├── pyproject.toml          ← uv workspace member; depends on movie-finder-chain
└── src/app/
    ├── main.py             FastAPI() + lifespan + /health
    ├── config.py           AppConfig (Pydantic Settings — reads from env / .env)
    ├── dependencies.py     get_current_user, get_store, get_graph
    ├── routers/
    │   ├── auth.py         POST /auth/register, /auth/login, /auth/refresh, /auth/logout
    │   └── chat.py         POST /chat, GET /chat/sessions, GET/DELETE /chat/{session_id}/…
    ├── auth/
    │   ├── middleware.py   JWT encode / decode (python-jose)
    │   └── models.py       User, UserInDB, Token Pydantic models
    └── session/
        └── store.py        PostgreSQL session store (asyncpg connection pool)
```

---

## Running locally

The app is part of the `backend/` uv workspace — run from the `backend/` root:

```bash
# 1. Start a local PostgreSQL container (first time only)
make db-start
# → PostgreSQL at localhost:5432, database: movie_finder, user: movie_finder

# 2. Copy and fill in .env (if not done already)
cp .env.example .env && $EDITOR .env
# Required: APP_SECRET_KEY, DATABASE_URL, ANTHROPIC_API_KEY, OPENAI_API_KEY,
#           QDRANT_ENDPOINT, QDRANT_API_KEY, QDRANT_COLLECTION

# 3. Start the dev server with hot-reload
make run-dev
# → http://localhost:8000
# → Interactive docs: http://localhost:8000/docs
```

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_SECRET_KEY` | ✅ | — | JWT signing secret |
| `DATABASE_URL` | ✅ | — | `postgresql://user:pass@host:5432/db` | # pragma: allowlist secret
| `APP_ENV` | ✗ | `development` | `development \| staging \| production` |
| `APP_PORT` | ✗ | `8000` | Server port |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✗ | `30` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ✗ | `7` | JWT refresh token lifetime |

The full list of required variables (including chain / Qdrant) is in [../.env.example](../.env.example).

---

## Database

User data (users, sessions, messages) is stored in **PostgreSQL** via an `asyncpg` connection pool. The `SessionStore` class (`session/store.py`) creates the three tables on startup using `CREATE TABLE IF NOT EXISTS`.

For local development, start the database with `make db-start`. To migrate existing data from a SQLite `movie_finder.db`, use `make db-migrate`.

In production the database is **Azure Database for PostgreSQL Flexible Server** — connection credentials are injected from Azure Key Vault as environment variables.

---

## Integration with chain

The app imports `chain.compile_graph` in the lifespan handler:

```python
from chain import compile_graph

graph = compile_graph()  # singleton per process
# Streaming: graph.astream_events(input, config={"configurable": {"thread_id": session_id}})
```

The graph is compiled once at startup and shared across all requests via the `get_graph` dependency.

---

## Testing

Tests live in `app/tests/`. They use:
- A real PostgreSQL database (`DATABASE_URL` env var, default `localhost:5432/movie_finder_test`)
- A fully mocked LangGraph (no chain or LLM calls)
- FastAPI's `dependency_overrides` for store and graph injection

```bash
# Requires a running PostgreSQL (make db-start uses a different DB name by default)
# For tests, start postgres and then:
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/movie_finder_test \ # pragma: allowlist secret
    uv run pytest app/tests/ -v
```

Or simply:
```bash
make db-start && make test-app
```
