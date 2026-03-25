# Claude Code — backend submodule

This is **`movie-finder-backend`** (`backend/`) — part of the Movie Finder project.
GitHub repo: `aharbii/movie-finder-backend` · Parent repo: `aharbii/movie-finder`

---

## What this submodule does

FastAPI backend — HTTP/SSE API layer and `uv` workspace root for all Python packages.

- **Auth:** JWT (python-jose, bcrypt) — 30-min access token, 7-day refresh token
- **Sessions:** PostgreSQL 16 via asyncpg connection pool
- **Streaming:** SSE (`StreamingResponse`) — proxies LangGraph pipeline events to the frontend
- **uv workspace:** `app/`, `chain/`, `imdbapi/` are members; `rag_ingestion/` is not
- **Pre-commit:** `backend/.pre-commit-config.yaml` — applies to all workspace members
- **Makefile:** `backend/Makefile` — common dev tasks (lint, test, build, run)

### Key source layout

```
app/src/          FastAPI application (routes, middleware, deps)
chain/src/        LangGraph pipeline
imdbapi/src/      Async IMDb REST client
rag_ingestion/    Standalone ingestion script (not workspace member)
pyproject.toml    uv workspace root + shared tool config (ruff, mypy, pytest)
.pre-commit-config.yaml
Makefile
Jenkinsfile
Dockerfile
```

---

## Full project context

### Submodule map

| Path | GitHub repo | Role |
|---|---|---|
| `.` (root) | `aharbii/movie-finder` | Parent — all cross-repo issues |
| `backend/` | `aharbii/movie-finder-backend` | **← you are here** |
| `backend/app/` | (nested) | FastAPI application layer |
| `backend/chain/` | `aharbii/movie-finder-chain` | LangGraph AI pipeline |
| `backend/imdbapi/` | `aharbii/imdbapi-client` | Async IMDb REST client |
| `backend/rag_ingestion/` | `aharbii/movie-finder-rag` | Offline embedding ingestion |
| `frontend/` | `aharbii/movie-finder-frontend` | Angular 21 SPA |
| `docs/` | `aharbii/movie-finder-docs` | MkDocs documentation |
| `infrastructure/` | `aharbii/movie-finder-infrastructure` | IaC / Azure provisioning |

### Technology stack

| Layer | Stack |
|---|---|
| Language | Python 3.13 |
| API | FastAPI 0.115+, `StreamingResponse` (SSE) |
| Auth | JWT (python-jose), bcrypt, PostgreSQL session store |
| Database | PostgreSQL 16, asyncpg (raw DDL — no Alembic yet, see #3) |
| Package manager | `uv` workspace root |
| Linting | `ruff` (line-length 100, rules: E/F/I/N/UP/B/C4/SIM) |
| Type checking | `mypy --strict` (Python 3.13) |
| Tests | `pytest --asyncio-mode=auto` |
| CI | Jenkins Multibranch → Azure Container Registry → Azure Container Apps |

### Environment variables (`.env.example`)

```
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DATABASE_URL
QDRANT_ENDPOINT, QDRANT_API_KEY, QDRANT_COLLECTION
EMBEDDING_MODEL, EMBEDDING_DIMENSION
ANTHROPIC_API_KEY, CLASSIFIER_MODEL, REASONING_MODEL
OPENAI_API_KEY
RAG_TOP_K=8, MAX_REFINEMENTS=3, IMDB_SEARCH_LIMIT=3, CONFIDENCE_THRESHOLD=0.3
KAGGLE_USERNAME, KAGGLE_KEY, VECTOR_STORE=qdrant
LANGSMITH_TRACING=false, LANGSMITH_ENDPOINT, LANGSMITH_API_KEY, LANGSMITH_PROJECT
APP_SECRET_KEY, APP_ENV=development, APP_PORT=8000
```

---

## Design patterns to follow

| Pattern | Where | Rule |
|---|---|---|
| **Dependency injection** | `app/` routes | Use FastAPI `Depends()` for db pool, current user, config, and chain client. Never instantiate shared resources inside route handlers. |
| **Repository** | Database layer | Data access (SELECT, INSERT, UPDATE) lives in repository classes. No raw SQL in route handlers or services. |
| **Configuration object** | `config.py` / Pydantic `BaseSettings` | All env vars loaded once at startup. Never `os.getenv()` inside business logic. |
| **Middleware chain** | FastAPI middleware | Cross-cutting concerns (CORS — see #9, rate limiting — see #4, auth) are middleware, not per-route logic. |
| **SSE as a stream** | Streaming route | The SSE endpoint is a thin proxy — it invokes the chain and forwards events. Business logic stays in `chain/`. |

**Open issues that affect patterns:** #2 (MemorySaver non-persistent), #3 (no Alembic), #4 (no rate limiting), #9 (no CORS), #12 (`UserInDB` exposes `hashed_password`). Reference these in any related change.

---

## Coding standards

- `mypy --strict` must pass across the entire workspace
- No `type: ignore` without an explanatory comment
- No bare `except:` — catch specific exceptions; use `HTTPException` for API errors
- Docstrings on all public functions, classes, and route handlers (Google style)
- No `print()` — use `logging`; no debug prints left in production code
- Async all the way — never call blocking I/O in an async context (no `time.sleep`, no sync DB calls)
- Route handlers are thin — validation in Pydantic schemas, business logic in services, data access in repositories
- Line length: 100 (`ruff`)

---

## Pre-commit hooks

`backend/.pre-commit-config.yaml` — install and run from the `backend/` workspace root.
This config covers `app/` code; `chain/`, `imdbapi/`, and `rag_ingestion/` each have their own.

```bash
uv run pre-commit install    # once per clone
uv run pre-commit run --all-files
```

| Hook | Notes |
|---|---|
| `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-case-conflict`, `check-merge-conflict` | File health |
| `check-added-large-files`, `check-illegal-windows-names`, `detect-private-key` | Safety |
| `detect-secrets` | No API keys or tokens |
| `mypy` (strict, Python 3.13, extra deps: `pydantic`, `pydantic-settings`, `fastapi`, excludes `tests/` and `conftest.py`) | Type checking |
| `ruff-check --fix`, `ruff-format` | Linting and formatting |

**Never `--no-verify`.** False-positive → `# pragma: allowlist secret` + `detect-secrets scan > .secrets.baseline`.

---

## Common Makefile targets

```bash
make lint       # ruff + mypy
make test       # pytest --asyncio-mode=auto
make build      # docker build
make run        # docker compose up
```

---

## VSCode setup

`backend/.vscode/` covers **all backend sub-packages** — opening `backend/` as a workspace
gives you full lint, test, debug, and format capabilities for app/, chain/, imdbapi/, and rag_ingestion/:

- `settings.json` — Python interpreter (`backend/.venv`), Ruff format-on-save, mypy strict, pytest
- `extensions.json` — Python, debugpy, Ruff, mypy, TOML, Docker, GitLens
- `launch.json` — FastAPI dev server · chain chat.py · rag pipeline · pytest all/current/rag
- `tasks.json` — per-package lint/test + aggregates (`lint: all`, `test: all`) + pre-commit per package

**Create the interpreter first:** `uv sync --all-packages` from `backend/` → creates `.venv/`
**rag_ingestion uses its own venv:** run `uv sync` from `backend/rag_ingestion/` separately.

---

## Session start protocol

1. `gh issue list --repo aharbii/movie-finder --state open`
2. Create issue in `aharbii/movie-finder`, then `aharbii/movie-finder-backend`
3. Create branch + work through checklist below

---

## Branching and commits

```
feature/<kebab>  fix/<kebab>  chore/<kebab>  docs/<kebab>  hotfix/<kebab>
```

Conventional Commits: `feat(app): add rate limiting middleware`

---

## Cross-cutting change checklist

### 1. GitHub issues
- [ ] `aharbii/movie-finder` (parent)
- [ ] `aharbii/movie-finder-backend` linked

### 2. Branch
- [ ] Branch in this repo + `chore/` in root `movie-finder` to bump pointer

### 3. ADR
- [ ] New external dependency, auth model change, or API contract decision?
  → `docs/architecture/decisions/ADR-NNN-title.md`

### 4. Implementation and tests
- [ ] Follows dependency injection, repository, and middleware patterns
- [ ] Route handlers are thin — business logic is not inline
- [ ] `ruff` + `mypy --strict` pass across the workspace
- [ ] Pre-commit hooks pass
- [ ] `pytest --asyncio-mode=auto` passes

### 5. Environment and secrets
- [ ] `.env.example` updated in: **this repo**, root `movie-finder`, `frontend/` if API config changed
- [ ] New secrets flagged for Azure Key Vault, Jenkins, `docs/devops-setup.md`

### 6. Docker
- [ ] `Dockerfile` updated (new deps, env vars)
- [ ] `docker-compose.yml` updated
- [ ] Root `docker-compose.yml` if service port or env changed

### 7. CI — Jenkins
- [ ] `Jenkinsfile` reviewed — new credentials or stages?

### 8. Architecture diagrams (in `docs/` submodule)
- [ ] **PlantUML** — `03-backend-architecture.puml`, auth sequences (`07`), SSE sequence (`08`)
  **Never generate `.mdj`** — user syncs to StarUML
- [ ] **Structurizr C4** — `workspace.dsl` if containers or relations changed
- [ ] Commit to `aharbii/movie-finder-docs` first

### 9. Documentation
- [ ] `docs/` pages (API docs, auth flow, database schema)
- [ ] OpenAPI schema: verify no unintended breaking changes at `/docs`
- [ ] `README.md` and `CHANGELOG.md` updated

### 10. Sibling submodules likely affected
| Submodule | Why |
|---|---|
| `backend/chain/` | Invocation interface, SSE event shape, state changes |
| `backend/app/` | Direct child — most route changes live here |
| `backend/imdbapi/` | IMDb integration surface |
| `frontend/` | API contract, SSE event fields, auth flow |
| `infrastructure/` | New Azure resources, new env vars, new secrets |
| `docs/` | API docs, DevOps setup, architecture |

### 11. Submodule pointer bump
```bash
# in root movie-finder
git add backend && git commit -m "chore(backend): bump to latest main"
```

### 12. Pull request
- [ ] PR in `aharbii/movie-finder-backend`
- [ ] PR in `aharbii/movie-finder` (pointer bump)
