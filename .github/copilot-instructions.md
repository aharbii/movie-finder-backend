# GitHub Copilot — movie-finder-backend

FastAPI backend workspace — HTTP/SSE API layer and uv workspace root for the Python packages consumed by the app.

> For full project context, persona prompts, and architecture reference: see root `.github/copilot-instructions.md`.

---

## Python standards

- Route handlers stay thin — orchestration only, no business logic
- Docstrings required on all route handlers (Google style)
- Async all the way — never call blocking I/O in an async context
- Tests: `pytest --asyncio-mode=auto`; no real network calls in unit tests
- Run `make help` for all available targets

---

## Design patterns

| Pattern                  | Where                 | Rule                                                                                                            |
| ------------------------ | --------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Dependency injection** | `app/` routes         | Use `Depends()` for db pool, current user, config, and graph. Never instantiate shared resources inside handlers. |
| **Repository**           | Database layer        | Data access lives in repository classes. No raw SQL in route handlers.                                          |
| **Configuration object** | `config.py`           | Load env vars once via Pydantic `BaseSettings`. Never scatter `os.getenv()` through business logic.             |
| **SSE proxy**            | `app/routers/chat.py` | The SSE endpoint is a thin proxy. Business logic stays in `chain/`.                                             |

---

## Key files

| Path                 | Description                                                         |
| -------------------- | ------------------------------------------------------------------- |
| `app/src/`           | FastAPI routes, auth (JWT), SSE streaming, PostgreSQL via asyncpg   |
| `chain/`             | LangGraph AI pipeline (submodule)                                   |
| `pyproject.toml`     | uv workspace root + shared tool config (ruff, mypy, pytest)         |
| `docker-compose.yml` | Local stack: `postgres` + `backend` services                        |
| `Makefile`           | Docker-only dev contract — run `make help` for all targets          |
