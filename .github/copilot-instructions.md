# GitHub Copilot — movie-finder-backend

FastAPI backend workspace for Movie Finder. This repo is the backend integration
root and currently defines the **Docker-only local development contract for the
backend app stack**.

Parent project: `aharbii/movie-finder` — create cross-repo tracker issues there first.

---

## Repo structure

| Path | Role |
|---|---|
| `app/` | FastAPI routes, auth (JWT), SSE streaming, PostgreSQL via asyncpg |
| `chain/` | LangGraph AI pipeline (submodule → `aharbii/movie-finder-chain`) |
| `imdbapi/` | Async IMDb REST client (submodule → `aharbii/imdbapi-client`) |
| `rag_ingestion/` | Offline embedding ingestion (submodule → `aharbii/movie-finder-rag`) |
| `Makefile` | Docker-only backend app targets: `init`, `up`, `down`, `logs`, `shell`, `lint`, `format`, `typecheck`, `test`, `test-coverage`, `pre-commit` |
| `docker-compose.yml` | backend app local stack (`postgres` + `backend`) |
| `Dockerfile` | dev + runtime images |
| `Jenkinsfile` | backend pipeline |

`rag_ingestion/` is a standalone child repo and is intentionally excluded from
the backend dev image in this iteration.

---

## Python standards

- Python 3.13, Docker-first local workflow
- `ruff` + `mypy --strict`, line length **100**
- Type annotations required on public functions and methods
- No bare `except:`
- No scattered `os.getenv()` in business logic
- Async all the way
- Docstrings on public classes and functions (Google style)
- Tests: `pytest --asyncio-mode=auto`; no real network calls in unit tests

---

## Design patterns — follow these

| Pattern | Where | Rule |
|---|---|---|
| **Dependency injection** | `app/` routes | `Depends()` for db pool, auth, config, graph |
| **Repository** | Database layer | No raw SQL in route handlers |
| **Configuration object** | All packages | Settings live in `config.py` / Pydantic `BaseSettings` |
| **SSE proxy** | `app/routers/chat.py` | Route streams events; business logic stays in `chain/` |

---

## Current iteration boundary

This repo now standardizes the backend app Docker contract only.

Do not take over the standalone child repo tooling from here yet:

- `movie-finder-chain#9`
- `imdbapi-client#3`
- `movie-finder-rag#13`

If a backend-root change depends on one of those repos, document the dependency
or handoff as an issue comment instead of silently expanding scope.

---

## Developer workflow

```bash
make init
make up
make down
make logs
make shell
make lint
make format
make typecheck
make test
make test-coverage
make pre-commit
```

VS Code workflow:

- run host tasks through `make ...`
- attach VS Code to the running `backend` container
- use `/opt/venv/bin/python` inside that container
- Python analysis should see `app/src`, `chain/src`, and `imdbapi/src`
- Python Test Explorer is configured for `app/tests/` only in this iteration

---

## Secret contract

Canonical Qdrant variables:

- `QDRANT_URL`
- `QDRANT_API_KEY_RO`
- `QDRANT_COLLECTION_NAME`
- `QDRANT_API_KEY_RW` (rag only)
- `KAGGLE_API_TOKEN` (rag only)

Do not reintroduce the old names in docs or `.env.example`. The backend compose
file may still export legacy aliases internally as a temporary bridge until the
child chain issue lands.

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
