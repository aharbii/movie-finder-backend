# OpenAI Codex CLI — backend submodule

Foundational mandate for the `movie-finder-backend` (`backend/`).

---

## What this submodule does
FastAPI backend — HTTP/SSE API layer and `uv` workspace root.
- **Auth:** JWT (python-jose, bcrypt)
- **Sessions:** PostgreSQL 16 via asyncpg
- **Streaming:** SSE proxies LangGraph pipeline events
- **uv workspace:** `app/`, `chain/`, `imdbapi/` are members

---

## Technology stack
- Python 3.13, FastAPI 0.115+
- `uv` workspace root
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
- `make lint`
- `make test`
- `make build` (Docker)
- `make run` (Docker Compose)

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

## VSCode setup

`backend/.vscode/` covers **all backend sub-packages** — opening `backend/` as a workspace
gives full lint, test, debug, and format capabilities for app/, chain/, imdbapi/, and rag_ingestion/.

- `settings.json` — interpreter `backend/.venv`, Ruff format-on-save, mypy strict
- `extensions.json` — Python, debugpy, Ruff, mypy, TOML, Docker, GitLens
- `launch.json` — FastAPI dev server · chain chat.py · rag pipeline · pytest all/per-package
- `tasks.json` — per-package lint/test + `lint: all` + `test: all` aggregates + pre-commit per package

**Interpreters:** `uv sync --all-packages` from `backend/` (workspace members);
`uv sync` from `backend/rag_ingestion/` separately (standalone project).

**Modifying VSCode configs:** keep the hierarchy — child task must be re-exposed in parent
with an explicit `options.cwd`. Update `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and the repo's
`.github/copilot-instructions.md` after.
