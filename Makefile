# =============================================================================
# Movie Finder Backend — Docker-only developer contract
#
# Scope of this Makefile:
#   - Backend app stack owned by this repo (app/ + local PostgreSQL)
#   - Source-mounted access to chain/ and imdbapi/, which the app imports
#
# Explicitly out of scope:
#   - Standalone child-repo workflows for chain/, imdbapi/, rag_ingestion/
#   - Parent-level orchestration of child-repo lint/test/build pipelines
#
# Usage:
#   make help
#   make <target>
#
# Typical first-time flow:
#   make init        # build image + create .env + install git hook
#   make up          # start full stack (postgres + backend)
#   make check       # lint + typecheck + tests with coverage
#
# When the backend container is already running, quality commands use
# 'docker compose exec' instead of a new container — faster for interactive dev.
# =============================================================================

.PHONY: help init up down logs shell lint format fix typecheck test test-coverage \
        pre-commit build run run-dev setup check editor-up editor-down ci-down detect-secrets \
        clean clean-docker

.DEFAULT_GOAL := help

COMPOSE ?= docker compose
SERVICE ?= backend
GIT_DIR_HOST := $(shell git rev-parse --git-dir)
GIT_HOOKS_DIR := $(GIT_DIR_HOST)/hooks

# Export so docker compose picks it up automatically (avoids per-command prefix).
export BACKEND_GIT_DIR := $(GIT_DIR_HOST)

# Tests run against a separate database inside the same postgres container so
# local app data survives a 'make test'.
DB_NAME ?= movie_finder
DB_USER ?= movie_finder
DB_PASSWORD ?= devpassword
TEST_DB_NAME ?= movie_finder_test
TEST_DATABASE_URL ?= postgresql://$(DB_USER):$(DB_PASSWORD)@postgres:5432/$(TEST_DB_NAME)

SOURCE_PATHS := app/src app/tests
COVERAGE_XML ?= coverage.xml
COVERAGE_HTML ?= htmlcov
JUNIT_XML ?= junit.xml

# ---------------------------------------------------------------------------
# exec when running, run --rm otherwise — avoids container startup overhead
# for interactive development while remaining correct for CI.
# ---------------------------------------------------------------------------
define exec_or_run
	@if $(COMPOSE) ps --services --status running 2>/dev/null | grep -qx "$(SERVICE)"; then \
		$(COMPOSE) exec $(SERVICE) $(1); \
	else \
		$(COMPOSE) run --rm --no-deps $(SERVICE) $(1); \
	fi
endef

help:
	@echo ""
	@echo "Movie Finder Backend — available targets"
	@echo "========================================="
	@echo ""
	@echo "  Setup"
	@echo "    init           Build image, create .env from template, install git hook"
	@echo ""
	@echo "  Editor"
	@echo "    editor-up      Start only the backend container for editing/linting"
	@echo "    editor-down    Stop the backend container and remove compose resources"
	@echo "    shell          Open a zsh shell in the backend container"
	@echo ""
	@echo "  Lifecycle"
	@echo "    up             Start full stack (postgres + backend) in the background"
	@echo "    down           Stop the local backend stack and remove containers"
	@echo "    logs           Follow backend + postgres logs"
	@echo "    ci-down        Full cleanup for CI: stop containers and remove volumes + local images"
	@echo ""
	@echo "  Quality"
	@echo "    lint           Run ruff check (report only)"
	@echo "    format         Run ruff format (apply)"
	@echo "    fix            Run ruff check --fix + ruff format (apply all auto-fixes)"
	@echo "    typecheck      Run mypy --strict"
	@echo "    test           Run pytest"
	@echo "    test-coverage  Run pytest with coverage XML/HTML output"
	@echo "    detect-secrets Run detect-secrets scan"
	@echo "    pre-commit     Run all pre-commit hooks"
	@echo "    check          lint + typecheck + test-coverage"
	@echo ""
	@echo "  Maintenance"
	@echo "    clean          Remove __pycache__, .pytest_cache, .mypy_cache, reports (via Docker)"
	@echo "    clean-docker   Stop containers and remove volumes + local images"
	@echo ""
	@echo "  Compatibility aliases"
	@echo "    build          Alias for init"
	@echo "    run / run-dev  Alias for editor-up"
	@echo "    setup          Alias for init"
	@echo ""

init:
	@if [ ! -f .env ]; then cp .env.example .env && echo ">>> .env created from .env.example"; fi
	$(COMPOSE) build $(SERVICE)
	@printf '#!/bin/sh\nexec make pre-commit\n' > $(GIT_HOOKS_DIR)/pre-commit
	@chmod +x $(GIT_HOOKS_DIR)/pre-commit
	@echo ">>> git pre-commit hook installed (calls 'make pre-commit' on every commit)"

build: init
setup: init

editor-up:
	$(COMPOSE) up -d $(SERVICE)

up: editor-up
run: editor-up
run-dev: editor-up

editor-down:
	$(COMPOSE) down --remove-orphans

down: editor-down

ci-down:
	$(COMPOSE) down -v --remove-orphans

logs:
	$(COMPOSE) logs -f $(SERVICE) postgres

shell:
	@if $(COMPOSE) ps --services --status running 2>/dev/null | grep -qx "$(SERVICE)"; then \
		$(COMPOSE) exec $(SERVICE) zsh; \
	else \
		$(COMPOSE) run --rm $(SERVICE) zsh; \
	fi

lint:
	$(call exec_or_run,ruff check $(SOURCE_PATHS))

format:
	$(call exec_or_run,ruff format $(SOURCE_PATHS))

fix:
	$(call exec_or_run,ruff check --fix $(SOURCE_PATHS))
	$(call exec_or_run,ruff format $(SOURCE_PATHS))

typecheck:
	$(call exec_or_run,mypy $(SOURCE_PATHS))

test:
	@if $(COMPOSE) ps --services --status running 2>/dev/null | grep -qx "$(SERVICE)"; then \
		$(COMPOSE) exec -e DATABASE_URL="$(TEST_DATABASE_URL)" $(SERVICE) \
			pytest app/tests/ --asyncio-mode=auto -v --tb=short; \
	else \
		$(COMPOSE) run --rm -e DATABASE_URL="$(TEST_DATABASE_URL)" $(SERVICE) \
			pytest app/tests/ --asyncio-mode=auto -v --tb=short; \
	fi

test-coverage:
	@if $(COMPOSE) ps --services --status running 2>/dev/null | grep -qx "$(SERVICE)"; then \
		$(COMPOSE) exec -e DATABASE_URL="$(TEST_DATABASE_URL)" $(SERVICE) \
			pytest app/tests/ --asyncio-mode=auto -v --tb=short \
			--cov=app \
			--cov-report=term-missing \
			--cov-report=xml:$(COVERAGE_XML) \
			--cov-report=html:$(COVERAGE_HTML) \
			--junitxml=$(JUNIT_XML); \
	else \
		$(COMPOSE) run --rm -e DATABASE_URL="$(TEST_DATABASE_URL)" $(SERVICE) \
			pytest app/tests/ --asyncio-mode=auto -v --tb=short \
			--cov=app \
			--cov-report=term-missing \
			--cov-report=xml:$(COVERAGE_XML) \
			--cov-report=html:$(COVERAGE_HTML) \
			--junitxml=$(JUNIT_XML); \
	fi

detect-secrets:
	$(call exec_or_run,detect-secrets scan --baseline .secrets.baseline)

pre-commit:
	$(call exec_or_run,pre-commit run --all-files)

check: lint typecheck test-coverage

clean:
	@echo ">>> Removing Python cache files (via Docker)..."
	$(call exec_or_run,find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true)
	$(call exec_or_run,find . -type d -name ".pytest_cache" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true)
	$(call exec_or_run,find . -type d -name ".mypy_cache" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true)
	$(call exec_or_run,find . -type d -name ".ruff_cache" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true)
	$(call exec_or_run,find . -name "*.egg-info" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true)
	$(call exec_or_run,find . -name "$(COVERAGE_XML)" -not -path "./.git/*" -delete 2>/dev/null || true)
	$(call exec_or_run,find . -name "$(JUNIT_XML)" -not -path "./.git/*" -delete 2>/dev/null || true)
	$(call exec_or_run,find . -type d -name "$(COVERAGE_HTML)" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true)
	@echo "Clean complete."

clean-docker: ci-down
