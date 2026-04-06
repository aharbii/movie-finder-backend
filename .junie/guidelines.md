# JetBrains AI (Junie) — backend submodule guidelines

This is **`movie-finder-backend`** (`backend/`) — FastAPI backend + uv workspace root.
GitHub repo: `aharbii/movie-finder-backend` · Parent: `aharbii/movie-finder`

---

## What this submodule does

FastAPI backend — HTTP/SSE API layer + auth + PostgreSQL session store.

- **Auth:** JWT (python-jose, bcrypt) — 30-min access token, 7-day refresh token
- **Sessions:** PostgreSQL 16 via asyncpg connection pool
- **Streaming:** SSE (`StreamingResponse`) — proxies LangGraph pipeline events to the frontend
- **uv workspace:** `app/` and `chain/` are workspace members

### Key layout

```
app/src/     FastAPI application (routes, middleware, deps)
chain/src/   LangGraph pipeline imported by the app
pyproject.toml  uv workspace root + shared ruff/mypy/pytest config
docker-compose.yml
Dockerfile
Makefile
Jenkinsfile
```

---

## Quality commands (Docker-only)

```bash
make pre-commit   # lint + typecheck + format inside Docker
make test         # pytest --asyncio-mode=auto inside Docker
make lint         # ruff check
make typecheck    # mypy --strict
make test-coverage
```

Never run quality tools on the host — always through Docker.

---

## Python standards

- Line length: 100 (`ruff` + `mypy`)
- `mypy --strict` must pass; no `type: ignore` without comment
- No bare `except:`, no `os.getenv()` in business logic
- Docstrings (Google style) on all public functions, classes, route handlers
- No `print()` in production code
- Async all the way
- Route handlers stay thin — logic lives in services or the chain

---

## Design patterns

| Pattern      | Where        | Rule                                                                |
| ------------ | ------------ | ------------------------------------------------------------------- |
| DI           | Routes       | `Depends()` for db pool, auth, config — never inside route handlers |
| Repository   | DB layer     | Data access in repository classes — no raw SQL in routes            |
| Config object| `config.py`  | `BaseSettings` loaded once at startup                               |
| Middleware   | Cross-cutting| Cross-cutting concerns belong in middleware, not per-route          |
| SSE proxy    | Streaming    | SSE endpoint is a thin proxy; business logic stays in `chain/`      |

---

## Environment variables

```
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DATABASE_URL
QDRANT_URL, QDRANT_API_KEY_RO, QDRANT_COLLECTION_NAME
ANTHROPIC_API_KEY, CLASSIFIER_MODEL, REASONING_MODEL
OPENAI_API_KEY
RAG_TOP_K, MAX_REFINEMENTS, IMDB_SEARCH_LIMIT, CONFIDENCE_THRESHOLD
LANGSMITH_TRACING, LANGSMITH_ENDPOINT, LANGSMITH_API_KEY, LANGSMITH_PROJECT
APP_SECRET_KEY, APP_ENV, APP_PORT
```

---

## Workflow

- Issues: create parent in `aharbii/movie-finder`, child here via `linked_task.yml`
- Branches: `feature/<kebab>`, `fix/<kebab>`, `chore/<kebab>`, `docs/<kebab>`
- Commits: Conventional Commits — `feat(app): add rate limiting middleware`
- Pre-commit: `make pre-commit` (Docker — never `uv run pre-commit` on host)
- Tests: `make test` or `make test-coverage`
- After merge: bump submodule pointer in parent `movie-finder`

---

## Submodule pointer bump

```bash
# in root movie-finder
git add backend && git commit -m "chore(backend): bump to latest main"
```
