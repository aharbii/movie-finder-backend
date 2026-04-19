# Claude Code — backend submodule

This is **`movie-finder-backend`** (`backend/`) — part of the Movie Finder project.
GitHub repo: `aharbii/movie-finder-backend` · Parent repo: `aharbii/movie-finder`

> See root `CLAUDE.md` for: full submodule map, GitHub issue/PR hygiene, cross-cutting checklist, coding standards, branching strategy, session start protocol.

---

## What this submodule does

FastAPI backend — HTTP/SSE API layer and backend integration root for the Python
packages consumed by the app.

- **Auth:** JWT (python-jose, bcrypt) — 30-min access token, 7-day refresh token
- **Sessions:** PostgreSQL 16 via asyncpg connection pool
- **Streaming:** SSE (`StreamingResponse`) — proxies LangGraph pipeline events to the frontend
- **uv workspace:** `app/` and `chain/` are members (`imdbapi/` is an independent path dependency)
- **Makefile:** `backend/Makefile` — Docker-only dev contract for the backend app stack
- **Pre-commit:** runs inside Docker via `make pre-commit`

### Key source layout

```text
app/src/          FastAPI application (routes, middleware, deps)
chain/src/        LangGraph pipeline imported by the app
imdbapi/          Independent submodule (imported by chain via path dependency)
pyproject.toml    uv workspace root + shared tool config (ruff, mypy, pytest)
docker-compose.yml
Dockerfile
Makefile
Jenkinsfile
```

---

## Technology stack (backend-specific)

| Layer           | Stack                                                     |
| --------------- | --------------------------------------------------------- |
| Language        | Python 3.13                                               |
| API             | FastAPI 0.115+, `StreamingResponse` (SSE)                 |
| Auth            | JWT (python-jose), bcrypt, PostgreSQL session store       |
| Database        | PostgreSQL 16, asyncpg                                    |
| Package manager | `uv` workspace root                                       |
| Local dev       | Docker Compose + attached-container VS Code workflow      |
| Tests           | `pytest --asyncio-mode=auto`, `pytest-cov`                |
| CI/CD           | Jenkins → Azure Container Registry → Azure Container Apps |

---

## Environment variables (`.env.example`)

```text
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DATABASE_URL
QDRANT_URL, QDRANT_API_KEY_RO, QDRANT_COLLECTION_NAME
ANTHROPIC_API_KEY, CLASSIFIER_MODEL, REASONING_MODEL
OPENAI_API_KEY
RAG_TOP_K, MAX_REFINEMENTS, IMDB_SEARCH_LIMIT, CONFIDENCE_THRESHOLD
LANGSMITH_TRACING, LANGSMITH_ENDPOINT, LANGSMITH_API_KEY, LANGSMITH_PROJECT
APP_SECRET_KEY, APP_ENV, APP_PORT, POSTGRES_HOST_PORT, BACKEND_HOST_PORT
```

Legacy Qdrant names may still appear in `docker-compose.yml` or Jenkins as a temporary
compatibility bridge until `movie-finder-chain#9`.

---

## Design patterns (backend-specific)

| Pattern                  | Where                                 | Rule                                                                                                                            |
| ------------------------ | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Dependency injection** | `app/` routes                         | Use FastAPI `Depends()` for db pool, current user, config, and graph. Never instantiate shared resources inside route handlers. |
| **Repository**           | Database layer                        | Data access lives in repository classes. No raw SQL in route handlers.                                                          |
| **Configuration object** | `config.py` / Pydantic `BaseSettings` | Load env vars once. Never scatter `os.getenv()` through business logic.                                                         |
| **Middleware chain**     | FastAPI middleware                    | Cross-cutting concerns belong in middleware, not repeated per route.                                                             |
| **SSE as a stream**      | Streaming route                       | The SSE endpoint is a thin proxy. Business logic stays in `chain/`.                                                             |

---

## Coding standards (additions to root CLAUDE.md)

- Route handlers stay thin — orchestration only, no business logic
- Docstrings required on all route handlers (Google style)
- Async all the way — never call blocking I/O in an async context

---

## Pre-commit hooks

`backend/.pre-commit-config.yaml` covers `app/`; `chain/` and `imdbapi/` each have their own.

```bash
make pre-commit
```

Hooks: whitespace/YAML/safety checks, `detect-secrets`, `mypy --strict`, `ruff-check --fix`, `ruff-format`. **Never `--no-verify`.**

---

## Common Makefile targets

```bash
make init / make up / make down / make ci-down
make logs / make shell / make editor-up / make editor-down
make lint / make format / make typecheck / make test / make test-coverage / make pre-commit
```

---

## VS Code setup

- `settings.json` — interpreter `/opt/venv/bin/python`; pytest discovery for `app/tests/`; extraPaths for `app/src`, `chain/src`, `imdbapi/src`
- `launch.json` — backend app + backend app tests inside the attached container
- `tasks.json` — host tasks that call `make <target>`
- `extensions.json` — Remote Containers, Pylance, Ruff, Docker, Makefile, Coverage Gutters

**Workflow:** run `make editor-up` (or `make up`), then attach VS Code to the running `backend` service container.

---

## Workflow invariants (backend-specific)

- Gitlink path is `backend` in `aharbii/movie-finder`. Parent path filters must use `backend`, not `backend/**`.
- `rag/` is no longer a backend submodule — it lives at the monorepo root; create issues in `aharbii/movie-finder-rag` directly from root.
- Do not use a backend iteration to take over child repo flows for `movie-finder-chain#9` or `imdbapi-client#3` — leave those to their own issues.

Run `/session-start` in root workspace.

---

## Cross-cutting change checklist (backend-specific rows)

| #   | Category           | Key gate                                                                                                                                                       |
| --- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Branch**         | `feature/fix/chore/docs` in this repo + pointer-bump `chore/` in root `movie-finder`                                                                           |
| 2   | **ADR**            | New external dep, auth model change, or API contract decision → ADR in `docs/`                                                                                 |
| 3   | **Env & secrets**  | `.env.example` updated here + root + `frontend/` if API changed; new secrets → Key Vault + Jenkins                                                             |
| 4   | **Docker**         | `Dockerfile` + `docker-compose.yml` updated for dep/env/port changes                                                                                           |
| 5   | **Diagrams**       | `03-backend-architecture.puml`, `07-seq-authentication.puml`, `08-seq-chat-sse.puml`; `workspace.dsl` if C4 changed; commit to `docs/` first; **never `.mdj`** |

### Sibling submodules likely affected

| Submodule                | Why                                                  |
| ------------------------ | ---------------------------------------------------- |
| `backend/chain/`         | Invocation interface, SSE event shape, state changes |
| `backend/chain/imdbapi/` | IMDb integration surface                             |
| `frontend/`              | API contract, SSE event fields, auth flow            |
| `infrastructure/`        | New Azure resources, new env vars, new secrets       |
| `docs/`                  | API docs, DevOps setup, architecture                 |

### Submodule pointer bump

```bash
# in root movie-finder
git add backend && git commit -m "chore(backend): bump to latest main"
```

### Pull request

- [ ] PR in `aharbii/movie-finder-backend` discloses the AI authoring tool + model
- [ ] PR in `aharbii/movie-finder` (pointer bump)
- [ ] Any AI-assisted review comment or approval discloses the review tool + model
