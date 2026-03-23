# =============================================================================
# Movie Finder Backend — Developer Makefile
#
# Usage:  make <target>
#         make help       ← list all targets with descriptions
#
# All Python commands run through uv to ensure the correct environment.
# Targets that need the workspace venv call `uv sync` before running.
# =============================================================================

.PHONY: help setup check lint lint-fix type-check \
        test test-chain test-imdbapi test-app test-rag test-all \
        run-dev \
        docker-up docker-down docker-chain docker-rag \
        submodules clean

# Default target
.DEFAULT_GOAL := help

WORKSPACE_PKGS  := chain/src imdbapi/src app/src rag_ingestion/src
WORKSPACE_TESTS := chain/tests imdbapi/tests app/tests rag_ingestion/tests

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
	@echo "  Code quality"
	@echo "    lint           ruff check + format check (chain + imdbapi)"
	@echo "    lint-fix       ruff auto-fix + format (chain + imdbapi)"
	@echo "    type-check     mypy only (chain + imdbapi)"
	@echo "    check          Quick smoke test: imports + lint (no network)"
	@echo ""
	@echo "  Testing"
	@echo "    test           pytest — all projects"
	@echo "    test-chain     pytest — chain only"
	@echo "    test-imdbapi   pytest — imdbapi only"
	@echo "    test-app       pytest — app only"
	@echo "    test-rag       pytest — rag_ingestion only"
	@echo ""
	@echo "  Docker"
	@echo "    docker-up      Start full stack (app + Qdrant)"
	@echo "    docker-down    Stop full stack"
	@echo "    docker-chain   Start chain dev stack (chain + Qdrant)"
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
		echo ""; \
	else \
		echo "  .env already exists — skipping copy."; \
	fi
	@echo ""
	@echo "Setup complete. Next steps:"
	@echo "  1. Edit .env with your API keys"
	@echo "  2. make docker-up    (start local stack)"
	@echo "  3. make check        (verify everything works)"
	@echo ""

submodules:
	git submodule update --remote --merge

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
# Docker
# --------------------------------------------------------------------------- #

docker-up:
	docker compose up -d
	@echo "Stack started."
	@echo "  Qdrant:  http://localhost:6333"
	@echo "  App:     http://localhost:8000  (placeholder until app/ is implemented)"

docker-down:
	docker compose down

docker-chain:
	cd chain && docker compose up -d
	@echo "Chain dev stack started."
	@echo "  Qdrant:  http://localhost:6333"

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
