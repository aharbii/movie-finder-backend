# Gemini CLI — backend submodule

Foundational mandate for the `movie-finder-backend` (`backend/`).

---

## What this submodule does

FastAPI backend — HTTP/SSE API layer and backend integration root.

- **Auth:** JWT (python-jose, bcrypt)
- **Sessions:** PostgreSQL 16 via asyncpg
- **Streaming:** SSE proxies LangGraph pipeline events
- **uv workspace:** `app/`, `chain/`, `imdbapi/` are members

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

## Coding standards

- `mypy --strict` must pass.
- Async all the way — no blocking I/O.
- Docstrings required (Google style).
- Line length: 100 (`ruff`).

---

## Common tasks

- `make init`
- `make up`
- `make down
- `make ci-down``
- `make logs`
- `make shell
- `make editor-up`
- `make editor-down``
- `make lint`
- `make format`
- `make typecheck`
- `make test`
- `make test-coverage`
- `make pre-commit`

---

## Current iteration boundary

This backend root now standardizes the Docker-only app workflow. Do not take
ownership of the standalone child repo surfaces from here yet:

- `movie-finder-chain#9`
- `imdbapi-client#3`
- `movie-finder-rag#13`

Record dependencies and handoffs as issue comments instead.

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

## VS Code setup

`backend/.vscode/` now separates host-run tasks from attached-container Python
tooling.

- `tasks.json` — host tasks that call `make <target>`
- `launch.json` — backend app + backend app test debug configs
- `settings.json` — interpreter `/opt/venv/bin/python`, pytest discovery for `app/tests/`,
  extraPaths for `app/src`, `chain/src`, and `imdbapi/src`
- `extensions.json` — Remote Containers, Pylance, Ruff, Docker, Makefile, Coverage Gutters

Run `make editor-up` (or `make up`), then attach VS Code to the running `backend` container.

Child repo debug/task surfaces remain owned by their own issues for now.

**Modifying VSCode configs:** update `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and
the repo's `.github/copilot-instructions.md` after.
