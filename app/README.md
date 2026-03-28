# app/ — FastAPI Application

FastAPI application that wraps the Movie Finder AI flow and exposes it over REST
and SSE with JWT authentication, PostgreSQL-backed sessions, and streaming chat.

This package is the **backend-owned application slice** that the root Docker-only
workflow standardizes in the current iteration.

---

## Implemented features

- **User authentication** — register / login / refresh / logout under `/auth/*`
- **Streaming chat** — `POST /chat` streams LangGraph events via SSE
- **Session management** — persistent conversation threads per user in PostgreSQL
- **Session history** — `GET /chat/{session_id}/history`
- **Session list** — `GET /chat/sessions`
- **Session delete** — `DELETE /chat/{session_id}`
- **Confirmed movie persistence** — the `qa` phase stores confirmed movie metadata
- **Health probes** — `/health`, `/health/live`, `/health/ready`

---

## Structure

```text
app/
├── pyproject.toml          uv workspace member consumed from the backend root
└── src/app/
    ├── main.py             FastAPI app + lifespan + health endpoints
    ├── config.py           AppConfig (Pydantic settings from env / .env)
    ├── dependencies.py     get_current_user, get_store, get_graph
    ├── routers/
    │   ├── auth.py         auth endpoints
    │   └── chat.py         streaming chat + session endpoints
    ├── auth/
    │   ├── middleware.py   JWT encode / decode helpers
    │   └── models.py       auth-related Pydantic models
    └── session/
        └── store.py        PostgreSQL session store via asyncpg
```

---

## Running locally

Run the app from the `backend/` root through the Docker-only contract:

```bash
cp .env.example .env
$EDITOR .env

make init
make up
```

Endpoints:

- API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`

If the parent `movie-finder/` stack is already using the default ports, override
`BACKEND_HOST_PORT` and `POSTGRES_HOST_PORT` in `.env` before `make up`.

Useful commands while developing:

```bash
make logs
make shell
make down
```

---

## Environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `APP_SECRET_KEY` | yes | JWT signing secret |
| `DATABASE_URL` | yes | canonical runtime database URL |
| `APP_ENV` | no | defaults to `development` |
| `APP_PORT` | no | defaults to `8000` |
| `QDRANT_URL` | yes | canonical Qdrant endpoint |
| `QDRANT_API_KEY_RO` | yes | read-only key for app + chain |
| `QDRANT_COLLECTION_NAME` | yes | shared collection identifier |
| `ANTHROPIC_API_KEY` | yes | required by the imported chain library |
| `OPENAI_API_KEY` | yes | required by the imported chain library |
| `LANGSMITH_*` | no | optional tracing |

The full cross-repo contract is documented in [../.env.example](../.env.example).

---

## Health endpoints

| Path | Purpose |
|------|---------|
| `/health` | backwards-compatible liveness alias |
| `/health/live` | container liveness probe |
| `/health/ready` | readiness probe that verifies the database pool |

`/health/ready` calls `SessionStore.ping()` and returns `503` if the database
cannot serve a simple query.

---

## Database

User data (users, sessions, messages) is stored in **PostgreSQL** via an
`asyncpg` connection pool. `SessionStore` creates the required tables on startup
using `CREATE TABLE IF NOT EXISTS`.

Local development details:

- `docker-compose.yml` starts a `postgres` service for the app
- `docker/postgres/init/01-create-test-database.sql` creates `movie_finder_test`
- `make test` points pytest at that dedicated test database

Production details:

- Azure Database for PostgreSQL Flexible Server
- canonical Key Vault secret name: `postgres-url`

If you need to migrate old local SQLite data, use
`scripts/migrate_sqlite_to_postgres.py` from an attached backend container so
the interpreter and dependencies match the supported Docker-only workflow.

---

## Integration with chain

The app compiles the LangGraph pipeline once during lifespan startup:

```python
from chain import compile_graph

graph = compile_graph()
```

That compiled graph is then shared across requests through dependency injection.

Current boundary:

- the app root workflow supports importing `chain` and `imdbapi`
- standalone child-repo task/debug surfaces are still owned by their own issues

---

## Testing

Tests live in `app/tests/`. They use:

- a real PostgreSQL database
- a mocked graph dependency
- FastAPI dependency overrides for store and graph injection

Run them through the backend root contract:

```bash
make test
make test-coverage
```

`make test-coverage` writes:

- `app-coverage.xml`
- `htmlcov/app/`

In VS Code, the Python Test Explorer is configured for `app/tests/` only in this
iteration, and the attached-container launch configs provide debug entry points
for the app test suite.
