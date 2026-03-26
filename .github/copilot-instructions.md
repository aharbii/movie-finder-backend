# GitHub Copilot — movie-finder-backend

FastAPI backend workspace for Movie Finder. This repo is a `uv` workspace root containing
four Python packages: `app/`, `chain/`, `imdbapi/`, and `rag_ingestion/`.

Parent project: `aharbii/movie-finder` — all issues created there first, then linked here.

---

## Repo structure

| Path | Role |
|---|---|
| `app/` | FastAPI routes, auth (JWT), SSE streaming, PostgreSQL via asyncpg |
| `chain/` | LangGraph 8-node AI pipeline (submodule → `aharbii/movie-finder-chain`) |
| `imdbapi/` | Async IMDb REST client (submodule → `aharbii/imdbapi-client`) |
| `rag_ingestion/` | Offline embedding ingestion (submodule → `aharbii/movie-finder-rag`) |
| `Makefile` | `make lint`, `make test`, `make lint-fix`, per-package targets |
| `pyproject.toml` | uv workspace root + shared tool config (ruff, mypy) |

`rag_ingestion/` is a **standalone uv project** (not a workspace member) — it has its own
`.venv`. All other packages share `backend/.venv` (`uv sync --all-packages` from this root).

---

## Python standards

- Python 3.13, `uv` workspace, `ruff` + `mypy --strict`, line length **100**
- Type annotations required on all public functions and methods
- No bare `except:` — catch specific exceptions
- No `os.getenv()` — use `config.py` + Pydantic `BaseSettings`
- Async all the way — never block an async context
- Docstrings on all public classes and functions (Google style)
- Tests: `pytest --asyncio-mode=auto`. Mock at HTTP boundary — no real network calls.

---

## Design patterns — follow these

| Pattern | Where | Rule |
|---|---|---|
| **Dependency injection** | `app/` routes | `Depends()` for db pool, auth, config — never instantiate inside handlers |
| **Repository** | Database layer | No raw SQL in route handlers — all data access in repository classes |
| **Configuration object** | All packages | Settings loaded once in `config.py` / Pydantic `BaseSettings` |
| **Adapter** | `imdbapi/` | Client maps raw HTTP responses to internal domain types |
| **Strategy** | Embedding providers | New provider = new class, no `if provider == "openai"` branching |
| **State machine** | `chain/` LangGraph | New behaviour = new node or edge, not branching inside existing nodes |
| **Factory** | `chain/graph.py` | Node construction centralised; nodes are pure functions |

---

## Pre-commit hooks

```bash
uv run pre-commit install     # once per clone
uv run pre-commit run --all-files
```

Hooks: `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-merge-conflict`,
`detect-private-key`, `detect-secrets`, `mypy --strict`, `ruff-check --fix`, `ruff-format`.
`app/` mypy config adds `fastapi` as an additional dep.

Never `--no-verify`.

---

## Makefile targets

```bash
make lint          # ruff + mypy (all packages)
make lint-fix      # ruff --fix + ruff format
make test          # all packages
make test-app      # FastAPI app (requires make db-start)
make test-chain    # LangGraph chain
make test-imdbapi  # IMDb client
make test-rag      # RAG ingestion
make db-start      # Start local PostgreSQL via Docker
```

---

## Known open issues (highest priority)

| # | Title |
|---|---|
| #2 | `MemorySaver` non-persistent — breaks multi-replica |
| #3 | No Alembic migrations, no DB indexes |
| #4 | No rate limiting on any endpoint |
| #5 | Refresh tokens cannot be revoked |
| #7 | OpenAI + Qdrant clients re-created per LangGraph node |
| #8 | IMDb retry base delay 30 s — blocks SSE stream |

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

## Cross-cutting — check for every change

1. GitHub issue in `aharbii/movie-finder` (parent) + linked child issue here only if this repo changes, using the current templates and recent examples
2. Branch: `feature/`, `fix/`, `chore/` (kebab-case) from `main` unless stacking is explicitly requested
3. ADR if tech stack, pattern, or external dependency changes
4. `.env.example` updated in affected repos
5. `Dockerfile` + `docker-compose.yml` updated
6. `Jenkinsfile` reviewed (new stages, credentials, env vars)
7. PlantUML diagrams in `docs/architecture/plantuml/` updated
8. Structurizr `docs/architecture/workspace.dsl` updated
9. All sibling submodules assessed for impact
10. Coverage must not regress
