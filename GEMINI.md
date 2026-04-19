# Gemini CLI — backend submodule

This is **`movie-finder-backend`** (`backend/`) — part of the Movie Finder project.
GitHub repo: `aharbii/movie-finder-backend` · Parent repo: `aharbii/movie-finder`

> See root GEMINI.md for: full submodule map, GitHub issue/PR hygiene, coding standards, branching strategy, session start protocol.

---

## What this submodule does

FastAPI backend — HTTP/SSE API layer and backend integration root.

- **Auth:** JWT (python-jose, bcrypt)
- **Sessions:** PostgreSQL 16 via asyncpg
- **Streaming:** SSE proxies LangGraph pipeline events
- **uv workspace:** `app/` and `chain/` are members (`imdbapi/` and `rag_ingestion/` are independent path dependencies)

---

## Technology stack

- Python 3.13, FastAPI 0.115+
- Docker-first local development from the backend root
- `ruff` (line-length 100), `mypy --strict`
- `pytest --asyncio-mode=auto`

---

## Design patterns

- **Dependency injection:** Use FastAPI `Depends()` for shared resources.
- **Repository:** Data access lives in repository classes.
- **Configuration:** Pydantic `BaseSettings` for env vars.
- **Middleware:** Cross-cutting concerns in middleware.

---

## Common Makefile targets

```bash
make init / make up / make down / make ci-down
make logs / make shell / make editor-up / make editor-down
make lint / make format / make typecheck / make test / make test-coverage / make pre-commit
```

---

## Current iteration boundary

This backend root now standardizes the Docker-only app workflow. Do not take
ownership of the standalone child repo surfaces from here yet:

- `movie-finder-chain#9`
- `imdbapi-client#3`
- `movie-finder-rag#13`

Record dependencies and handoffs as issue comments instead.

---

## VS Code setup

`backend/.vscode/` separates host-run tasks from attached-container Python tooling.

- `tasks.json` — host tasks that call `make <target>`
- `launch.json` — backend app + backend app test debug configs
- `settings.json` — interpreter `/opt/venv/bin/python`, pytest discovery for `app/tests/`,
  extraPaths for `app/src`, `chain/src`, and `imdbapi/src`
- `extensions.json` — Remote Containers, Pylance, Ruff, Docker, Makefile, Coverage Gutters

**Workflow:** run `make editor-up` (or `make up`), then attach VS Code to the running `backend` container.

---

## Workflow invariants (backend-specific)

- Gitlink path is `backend` in `aharbii/movie-finder`. Parent path filters must use `backend`, not `backend/**`.
- `rag/` is a direct root submodule — create issues in `aharbii/movie-finder-rag` from root, not from here.

### Submodule pointer bump

```bash
# in root movie-finder
git add backend && git commit -m "chore(backend): bump to latest main"
```
