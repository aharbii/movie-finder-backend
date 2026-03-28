# Changelog — movie-finder-backend

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added

- Docker-only backend-root coverage workflow via `make test-coverage`
- Local postgres bootstrap SQL for the dedicated `movie_finder_test` database
- `/health/live` and `/health/ready` probes for container liveness and database readiness

### Changed

- Standardized the backend root on a Docker-only local development contract for the app stack
- Restored detailed inline guidance across the backend docs, scripts, VS Code config, and agent instruction files
- Updated Jenkins and Azure provisioning to the canonical Qdrant secret names from the infrastructure contract
- Clarified that child repo standalone workflows remain owned by their own issues in this iteration

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
