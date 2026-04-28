# Changelog — movie-finder-backend

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added

- Targeted chain runtime configuration for classifier, reasoning, embedding,
  and vector-store providers, including Docker `WITH_PROVIDERS` image extras
  for lean provider-specific backend images
- Docker-only backend-root coverage workflow via `make test-coverage`, now
  enforcing 100% line and branch coverage for the FastAPI app slice
- Local postgres bootstrap SQL for the dedicated `movie_finder_test` database
- `/health/live` and `/health/ready` probes for container liveness and database readiness
- Alembic migration workflow and Docker-backed database Make targets
- Refresh-token logout and revocation support
- Route-level rate limiting, CORS configuration, and chat message length validation
- `app/src/app/logging_config.py` — centralised `configure_logging()` bootstrap (idempotent,
  reads `LOG_LEVEL` / `LOG_FORMAT`, configures `app`, `chain`, `imdbapi`, `rag` namespaces,
  suppresses noisy HTTP library loggers)
- `LOG_FORMAT` env var documented in `.env.example` — `text` (default) or `json` for
  Azure Monitor / structured log pipelines
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) mirroring Jenkins 1:1:
  Lint · Typecheck · Test · Coverage reporting via `EnricoMi/publish-unit-test-result-action@v2`,
  `irongut/CodeCoverageSummary@v1.3.0`, and `marocchino/sticky-pull-request-comment@v2`

### Changed

- Backend startup now injects validated `AppConfig` into the chain runtime so
  the deployed container can switch provider/model/vector-store combinations
  without relying on host-local configuration
- Dockerized pre-commit now mounts nested submodule Git metadata correctly and
  excludes the `chain` gitlink from backend `detect-secrets` scans
- Standardized the backend root on a Docker-only local development contract for the app stack
- Restored detailed inline guidance across the backend docs, scripts, VS Code config, and agent instruction files
- Updated Jenkins and GitHub Actions coverage gates to require 100% line and branch coverage
- Clarified that child repo standalone workflows remain owned by their own issues in this iteration
- Replaced raw startup DDL with migrated PostgreSQL schema using UUID, TIMESTAMPTZ, JSONB, and supporting indexes
- Paginated `/chat/sessions` responses and narrowed authenticated route user objects to `UserOut`
- `app/src/app/main.py` now calls `configure_logging()` before the FastAPI app is assembled
- All test outputs (`junit.xml`, `coverage.xml`, `htmlcov/`) now written to a `reports/`
  subdirectory; `docker-compose.yml` uses a directory bind-mount (`./reports:/workspace/reports`)
  instead of individual file bind-mounts, fixing a Docker bug where missing host files were
  auto-created as directories causing `--junitxml must be a filename` errors
- `Jenkinsfile` — renamed "Chain Coverage" label to "Backend Coverage"; fixed `sourceDirectories`
  from `[[path: 'app/src']]` to `[[path: 'app']]` so Jenkins correctly resolves source file
  paths from coverage.xml; removed Build App Image stage (image builds now orchestrated by the
  root `aharbii/movie-finder` pipeline); updated all report paths to `reports/`
- Coverage config (`pyproject.toml`) — `source = ["app/src"]` + `relative_files = true` so
  coverage.xml emits workspace-relative paths instead of absolute Docker container paths

---

## [0.1.0] — 2026-03-22

### Added

- Multi-repo monorepo structure: `chain`, `imdbapi`, `rag_ingestion` as git submodules
- `uv` workspace integrating `chain` and `imdbapi` as workspace members
- Root `pyproject.toml` with shared `ruff`, `mypy`, and `pytest` configuration
- `Makefile` — developer shorthand: `setup`, `lint`, `lint-fix`, `test`, `test-all`,
  `docker-up`, `docker-down`, `docker-chain`, `docker-rag`, `clean`, `submodules`
- `scripts/setup.sh` — automated new-member onboarding with prerequisite checks
- `Dockerfile` — placeholder multi-stage image for future FastAPI app
- `docker-compose.yml` — full-stack local dev: app (port 8000) + Qdrant (port 6333)
- `Jenkinsfile` — integration CI: parallel lint/test for all packages, app image build,
  manual staging deploy (`DEPLOY_STAGING` parameter)
- `.env.example` — master environment template, all variables grouped by owning team
- `README.md` — project overview, architecture diagram, quick start, team onboarding table
- `CONTRIBUTING.md` — branching strategy, conventional commits, PR process, release flow
- `INTEGRATION.md` — team workflow, Qdrant secret sharing, submodule update guide, FAQ
- `app/README.md` — FastAPI application placeholder (future implementation)
- `.github/PULL_REQUEST_TEMPLATE.md` — PR checklist for all teams
- `.editorconfig` — cross-editor formatting consistency
- `.python-version` = `3.13` in all project roots
- Standardized `[dependency-groups]` (lint / test / dev) across all `pyproject.toml` files
- `[tool.uv] default-groups = []` in all projects — production installs are clean by default
- Consistent `.gitignore` across all repos: Python artifacts, build outputs, secrets, logs
