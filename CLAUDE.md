# Claude Code — backend submodule

This is **`movie-finder-backend`** (`backend/`) — part of the Movie Finder project.
GitHub repo: `aharbii/movie-finder-backend` · Parent repo: `aharbii/movie-finder`

---

## What this submodule does

FastAPI backend — HTTP/SSE API layer and backend integration root for the Python
packages consumed by the app.

- **Auth:** JWT (python-jose, bcrypt) — 30-min access token, 7-day refresh token
- **Sessions:** PostgreSQL 16 via asyncpg connection pool
- **Streaming:** SSE (`StreamingResponse`) — proxies LangGraph pipeline events to the frontend
- **uv workspace:** `app/` and `chain/` are members (`imdbapi/` and `rag_ingestion/` are independent path dependencies)
- **Makefile:** `backend/Makefile` — Docker-only dev contract for the backend app stack
- **Pre-commit:** runs inside Docker via `make pre-commit`

### Key source layout

```text
app/src/          FastAPI application (routes, middleware, deps)
chain/src/        LangGraph pipeline imported by the app
imdbapi/          Independent submodule (imported by chain via path dependency)
rag_ingestion/    Standalone child repo (not part of the backend dev image)
pyproject.toml    uv workspace root + shared tool config (ruff, mypy, pytest)
docker-compose.yml
Dockerfile
Makefile
Jenkinsfile
```

---

## Full project context

### Submodule map

| Path | GitHub repo | Role |
|---|---|---|
| `.` (root) | `aharbii/movie-finder` | Parent — cross-repo planning and issue tracking |
| `backend/` | `aharbii/movie-finder-backend` | **← you are here** |
| `backend/app/` | (nested) | FastAPI application layer |
| `backend/chain/` | `aharbii/movie-finder-chain` | LangGraph AI pipeline |
| `backend/imdbapi/` | `aharbii/imdbapi-client` | Async IMDb REST client |
| `backend/rag_ingestion/` | `aharbii/movie-finder-rag` | Offline embedding ingestion |
| `frontend/` | `aharbii/movie-finder-frontend` | Angular SPA |
| `docs/` | `aharbii/movie-finder-docs` | Architecture + docs |
| `infrastructure/` | `aharbii/movie-finder-infrastructure` | IaC / Azure provisioning |

### Technology stack

| Layer | Stack |
|---|---|
| Language | Python 3.13 |
| API | FastAPI 0.115+, `StreamingResponse` (SSE) |
| Auth | JWT (python-jose), bcrypt, PostgreSQL session store |
| Database | PostgreSQL 16, asyncpg |
| Vector store | Qdrant Cloud (external only) |
| Package manager | `uv` workspace root |
| Local dev | Docker Compose + attached-container VS Code workflow |
| Linting | `ruff` |
| Type checking | `mypy --strict` |
| Tests | `pytest --asyncio-mode=auto`, `pytest-cov` |
| CI/CD | Jenkins → Azure Container Registry → Azure Container Apps |

### Environment variables (`.env.example`)

```text
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DATABASE_URL
QDRANT_URL, QDRANT_API_KEY_RO, QDRANT_COLLECTION_NAME
QDRANT_API_KEY_RW, KAGGLE_API_TOKEN   # documented for cross-repo alignment only
ANTHROPIC_API_KEY, CLASSIFIER_MODEL, REASONING_MODEL
OPENAI_API_KEY
RAG_TOP_K, MAX_REFINEMENTS, IMDB_SEARCH_LIMIT, CONFIDENCE_THRESHOLD
LANGSMITH_TRACING, LANGSMITH_ENDPOINT, LANGSMITH_API_KEY, LANGSMITH_PROJECT
APP_SECRET_KEY, APP_ENV, APP_PORT, POSTGRES_HOST_PORT, BACKEND_HOST_PORT
```

Legacy Qdrant names may still appear inside `docker-compose.yml` or Jenkins only
as a temporary compatibility bridge until `movie-finder-chain#9`.

---

## Current iteration boundary

This repo now standardizes the **backend app Docker contract** from the root.

Do not use this iteration to take over the standalone child repo flows for:

- `movie-finder-chain#9`
- `imdbapi-client#3`
- `movie-finder-rag#13`

If the backend root needs to reference those repos:

1. keep the root change narrowly backend-owned
2. document the handoff or dependency as an issue comment
3. leave the child repo implementation to its own issue

---

## Design patterns to follow

| Pattern | Where | Rule |
|---|---|---|
| **Dependency injection** | `app/` routes | Use FastAPI `Depends()` for db pool, current user, config, and graph. Never instantiate shared resources inside route handlers. |
| **Repository** | Database layer | Data access lives in repository classes. No raw SQL in route handlers. |
| **Configuration object** | `config.py` / Pydantic `BaseSettings` | Load env vars once. Never scatter `os.getenv()` through business logic. |
| **Middleware chain** | FastAPI middleware | Cross-cutting concerns belong in middleware, not repeated per route. |
| **SSE as a stream** | Streaming route | The SSE endpoint is a thin proxy. Business logic stays in `chain/`. |

---

## Coding standards

- `mypy --strict` must pass
- No `type: ignore` without an explanatory comment
- No bare `except:`
- Docstrings on public functions, classes, and route handlers (Google style)
- No `print()` in production code
- Async all the way
- Route handlers stay thin
- Line length: 100 (`ruff`)

---

## Pre-commit hooks

`backend/.pre-commit-config.yaml` covers `app/`; `chain/`, `imdbapi/`, `rag_ingestion/` each have their own.


```bash
make pre-commit
```

Hooks: whitespace/YAML/safety checks, `detect-secrets`, `mypy --strict` (pydantic + fastapi deps), `ruff-check --fix`, `ruff-format`. **Never `--no-verify`.**
False positive → `# pragma: allowlist secret` + `detect-secrets scan > .secrets.baseline`.

---

## Common Makefile targets

```bash
make init
make up
make down
make ci-down
make logs
make shell
make editor-up
make editor-down
make lint
make format
make typecheck
make test
make test-coverage
make pre-commit
```

All supported root-level developer workflows execute through Docker Compose.

---

## VS Code setup

`backend/.vscode/` now separates host-run tasks from attached-container Python
tooling:

- `tasks.json` — host tasks that call `make <target>`
- `launch.json` — backend app + backend app tests inside the attached container
- `settings.json` — interpreter `/opt/venv/bin/python`, pytest discovery for `app/tests/`,
  extraPaths for `app/src`, `chain/src`, `imdbapi/src`
- `extensions.json` — Remote Containers, Pylance, Ruff, Docker, Makefile, Coverage Gutters

**Workflow:** run `make editor-up` (or `make up`), then attach VS Code to the running `backend`
service container.

**Scope note:** code navigation includes `chain/` and `imdbapi/` because the
backend app imports them directly, but the child repos' standalone task/debug
surfaces remain owned by their own issues.

---

## Workflow invariants

- This repo is the gitlink path `backend` inside `aharbii/movie-finder`. Parent
  workflow/path filters must use `backend`, not `backend/**`.
- Cross-repo tracker issues originate in `aharbii/movie-finder`. Create the linked child issue in
  this repo only if this repo will actually change.
- Inspect `.github/ISSUE_TEMPLATE/*.yml`, `.github/PULL_REQUEST_TEMPLATE.md`, and a recent
  example before creating or editing issues/PRs. Do not improvise titles or bodies.
- For child issues in this repo, use `.github/ISSUE_TEMPLATE/linked_task.yml` and keep the
  description, file references, and acceptance criteria repo-specific.
- If CI, required checks, or merge policy changes affect this repo, update contributor-facing docs
  here and in `aharbii/movie-finder` where relevant.
- If a new standalone issue appears mid-session, branch from `main` unless stacking is explicitly
  requested.
- PR descriptions must disclose the AI authoring tool + model. Any AI-assisted review comment or
  approval must also disclose the review tool + model.

---

## Cross-cutting change checklist

Full detail in `ai-context/issue-agent-briefing-template.md`.

| # | Category | Key gate |
|---|---|---|
| 1 | **Issues** | Parent `aharbii/movie-finder` + child here only if this repo changes; templates inspected |
| 2 | **Branch** | `feature/fix/chore/docs` in this repo + pointer-bump `chore/` in root `movie-finder` |
| 3 | **ADR** | New external dep, auth model change, or API contract decision → ADR in `docs/` |
| 4 | **Implementation** | DI / Repository / Middleware patterns; thin route handlers; `ruff`+`mypy --strict` pass; pre-commit pass |
| 5 | **Tests** | `pytest --asyncio-mode=auto` passes; coverage doesn't regress |
| 6 | **Env & secrets** | `.env.example` updated here + root + `frontend/` if API changed; new secrets → Key Vault + Jenkins |
| 7 | **Docker** | `Dockerfile` + `docker-compose.yml` updated for dep/env/port changes |
| 8 | **CI** | `Jenkinsfile` / `.github/workflows/` reviewed for new creds or stages |
| 9 | **Diagrams** | `03-backend-architecture.puml`, `07-seq-authentication.puml`, `08-seq-chat-sse.puml`; `workspace.dsl` if C4 changed; commit to `docs/` first; **never `.mdj`** |
| 9a | **Docs** | `docs/` pages updated; OpenAPI verified; `README.md` + `CHANGELOG.md` updated |

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
- [ ] PR in `aharbii/movie-finder-backend` discloses the AI authoring tool + model
- [ ] PR in `aharbii/movie-finder` (pointer bump)
- [ ] Any AI-assisted review comment or approval discloses the review tool + model
