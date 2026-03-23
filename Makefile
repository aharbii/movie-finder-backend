# =============================================================================
# Movie Finder Backend — Developer Makefile
#
# Usage:  make <target>
#         make help       ← list all targets with descriptions
#
# All Python commands run through uv to ensure the correct environment.
# Targets that need the workspace venv call `uv sync` before running.
#
# Local database (standalone — no full-stack compose needed):
#   make db-start    Start a local PostgreSQL container  (port 5432)
#   make db-stop     Stop and remove it
#   make db-reset    Wipe data and restart (clean slate)
#   make db-migrate  Migrate existing SQLite dev data into PostgreSQL
# =============================================================================

.PHONY: help setup check lint lint-fix type-check \
        test test-ci test-chain test-imdbapi test-app test-rag test-all \
        run-dev \
        db-start db-stop db-reset db-migrate \
        docker-up docker-down \
        submodules clean

# Default target
.DEFAULT_GOAL := help

WORKSPACE_PKGS  := chain/src imdbapi/src app/src rag_ingestion/src
WORKSPACE_TESTS := chain/tests imdbapi/tests app/tests rag_ingestion/tests

# Local postgres container defaults (override via env or .env)
DB_CONTAINER  ?= movie-finder-db
DB_NAME       ?= movie_finder
DB_USER       ?= movie_finder
DB_PASSWORD   ?= devpassword
DB_PORT       ?= 5432
DATABASE_URL  ?= postgresql://$(DB_USER):$(DB_PASSWORD)@localhost:$(DB_PORT)/$(DB_NAME)

# --------------------------------------------------------------------------- #
# Help
# --------------------------------------------------------------------------- #

help:
	@echo ""
	@echo "Movie Finder Backend — available targets"
	@echo "========================================="
	@echo ""
	@echo "  Setup"
	@echo "    setup          First-time dev setup (deps + pre-commit + .env)"
	@echo "    submodules     Pull latest from all submodule remotes"
	@echo "    run-dev        Start FastAPI dev server with hot-reload"
	@echo ""
	@echo "  Local database (standalone — no full-stack compose needed)"
	@echo "    db-start       Start a local PostgreSQL container (port $(DB_PORT))"
	@echo "    db-stop        Stop and remove the local PostgreSQL container"
	@echo "    db-reset       Wipe data and restart (fresh empty database)"
	@echo "    db-migrate     Migrate existing SQLite dev data → PostgreSQL"
	@echo ""
	@echo "  Code quality"
	@echo "    lint           ruff check + format check"
	@echo "    lint-fix       ruff auto-fix + format"
	@echo "    type-check     mypy"
	@echo "    check          Quick smoke test: imports + lint (no network)"
	@echo ""
	@echo "  Testing"
	@echo "    test           pytest — all projects (human-friendly)"
	@echo "    test-ci        pytest — all projects, JUnit XML → test-results/"
	@echo "    test-chain     pytest — chain only"
	@echo "    test-imdbapi   pytest — imdbapi only"
	@echo "    test-app       pytest — app only  (requires db-start)"
	@echo "    test-rag       pytest — rag_ingestion only"
	@echo ""
	@echo "  Full-stack Docker (from repo root, not here)"
	@echo "    docker-up      Start full stack via root docker-compose.yml"
	@echo "    docker-down    Stop full stack"
	@echo ""
	@echo "  Maintenance"
	@echo "    clean          Remove __pycache__, .pytest_cache, .mypy_cache, egg-info"
	@echo ""

# --------------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------------- #

setup:
	@echo ">>> Initializing git submodules..."
	git submodule update --init --recursive
	@echo ">>> Installing workspace packages with dev tools..."
	uv sync --group dev
	@echo ">>> Installing pre-commit hooks..."
	uv run pre-commit install
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ""; \
		echo "  .env created from .env.example."; \
		echo "  Fill in your API keys before running the application."; \
		echo "  Then run: make db-start  (starts local PostgreSQL)"; \
		echo ""; \
	else \
		echo "  .env already exists — skipping copy."; \
	fi
	@echo ""
	@echo "Setup complete. Next steps:"
	@echo "  1. Edit .env with your API keys"
	@echo "  2. make db-start     (start local PostgreSQL)"
	@echo "  3. make run-dev      (start FastAPI dev server)"
	@echo "  4. make check        (verify everything works)"
	@echo ""

submodules:
	git submodule update --remote --merge

# --------------------------------------------------------------------------- #
# Local PostgreSQL (standalone backend dev — no full-stack compose needed)
# --------------------------------------------------------------------------- #

db-start:
	@echo ">>> Starting local PostgreSQL container ($(DB_CONTAINER))..."
	docker run -d \
		--name $(DB_CONTAINER) \
		-p $(DB_PORT):5432 \
		-e POSTGRES_DB=$(DB_NAME) \
		-e POSTGRES_USER=$(DB_USER) \
		-e POSTGRES_PASSWORD=$(DB_PASSWORD) \
		postgres:16-alpine
	@echo ""
	@echo "  PostgreSQL running at localhost:$(DB_PORT)"
	@echo "  DATABASE_URL: postgresql://$(DB_USER):$(DB_PASSWORD)@localhost:$(DB_PORT)/$(DB_NAME)"
	@echo ""
	@echo "  Set this in your .env file as DATABASE_URL, then run: make run-dev"
	@echo ""

db-stop:
	@echo ">>> Stopping local PostgreSQL container ($(DB_CONTAINER))..."
	docker stop $(DB_CONTAINER) && docker rm $(DB_CONTAINER) || true

db-reset: db-stop db-start
	@echo ">>> Local PostgreSQL reset (data wiped)."

db-migrate:
	@echo ">>> Migrating SQLite dev data → PostgreSQL..."
	@echo "    Source: movie_finder.db"
	@echo "    Target: $(DATABASE_URL)"
	uv sync --frozen --quiet
	DATABASE_URL="$(DATABASE_URL)" uv run python scripts/migrate_sqlite_to_postgres.py movie_finder.db

# --------------------------------------------------------------------------- #
# Code quality
# --------------------------------------------------------------------------- #

lint:
	uv sync --frozen --group lint --quiet
	uv run ruff check $(WORKSPACE_PKGS) $(WORKSPACE_TESTS)
	uv run ruff format --check $(WORKSPACE_PKGS) $(WORKSPACE_TESTS)

lint-fix:
	uv sync --frozen --group lint --quiet
	uv run ruff check --fix $(WORKSPACE_PKGS) $(WORKSPACE_TESTS)
	uv run ruff format $(WORKSPACE_PKGS) $(WORKSPACE_TESTS)

type-check:
	uv sync --frozen --group lint --quiet
	uv run mypy $(WORKSPACE_PKGS)

check:
	@echo ">>> Checking workspace imports..."
	uv run python -c "from chain import compile_graph; print('  chain OK')"
	uv run python -c "from imdbapi import IMDBAPIClient; print('  imdbapi OK')"
	uv run python -c "from app.main import app; print('  app OK')"
	@echo ">>> Running lint..."
	@$(MAKE) lint
	@echo ">>> All checks passed."

# --------------------------------------------------------------------------- #
# Dev server
# --------------------------------------------------------------------------- #

run-dev:
	uv sync --group dev --quiet
	uv run fastapi dev app/src/app/main.py --port $${APP_PORT:-8000}

# --------------------------------------------------------------------------- #
# Testing
# --------------------------------------------------------------------------- #

test:
	uv sync --frozen --group test --quiet
	uv run pytest $(WORKSPACE_TESTS) -v --tb=short

test-ci:
	mkdir -p test-results
	uv sync --frozen --group test --quiet
	APP_SECRET_KEY=ci-test-only uv run pytest $(WORKSPACE_TESTS) \
	    --junitxml=test-results/results.xml \
	    -v --tb=short

test-chain:
	uv sync --frozen --group test --quiet
	uv run pytest chain/tests/ -v --tb=short

test-imdbapi:
	uv sync --frozen --group test --quiet
	uv run pytest imdbapi/tests/ -v --tb=short

test-app:
	uv sync --frozen --group test --quiet
	uv run pytest app/tests/ -v --tb=short

test-rag:
	uv sync --frozen --group test --quiet
	uv run pytest rag_ingestion/tests/ -v --tb=short

# --------------------------------------------------------------------------- #
# Full-stack Docker  (these targets drive the root-level docker-compose.yml)
# --------------------------------------------------------------------------- #

docker-up:
	cd .. && docker compose up -d
	@echo "Full stack started (from root docker-compose.yml)."
	@echo "  PostgreSQL: localhost:5432"
	@echo "  Backend:    http://localhost:8000"
	@echo "  Frontend:   http://localhost:80"

docker-down:
	cd .. && docker compose down

# --------------------------------------------------------------------------- #
# Maintenance
# --------------------------------------------------------------------------- #

clean:
	@echo ">>> Removing Python cache files..."
	find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.egg-info" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
	find . -name "coverage.xml" -not -path "./.git/*" -delete 2>/dev/null || true
	find . -name "test-results.xml" -not -path "./.git/*" -delete 2>/dev/null || true
	@echo "Clean complete."
