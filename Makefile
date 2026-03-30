# =============================================================================
# Movie Finder Backend — Docker-only developer contract
#
# Scope of this Makefile:
#   - Backend app stack owned by this repo (`app/` + local PostgreSQL)
#   - Source-mounted access to `chain/` and `imdbapi/`, which the app imports
#
# Explicitly out of scope for this iteration:
#   - Standalone child-repo workflows for `chain/`, `imdbapi/`, `rag_ingestion`
#   - Parent-level orchestration of child-repo lint/test/build pipelines
#
# Those repo-local extensions are tracked in:
#   movie-finder-chain#9, imdbapi-client#3, movie-finder-rag#13
#
# Usage:
#   make help
#   make <target>
#
# All supported developer commands execute through Docker Compose so the backend
# can run beside the parent `movie-finder/` stack without host-Python drift.
# =============================================================================

.PHONY: help init up down logs shell lint format typecheck test test-coverage \
        pre-commit build run run-dev setup check editor-up editor-down ci-down detect-secrets

.DEFAULT_GOAL := help

COMPOSE ?= docker compose
SERVICE ?= backend

# Git metadata resolution:
# When this repo is a submodule (inside movie-finder), its .git is a file
# pointing to a directory in the parent. We resolve the TRUE path on the host
# so it can be mounted into the container for pre-commit / versioning tools.
GIT_DIR_HOST := $(shell git rev-parse --git-dir)

# Tests run against a separate database inside the same postgres container so
# local app data survives a `make test`.
DB_NAME ?= movie_finder
DB_USER ?= movie_finder
DB_PASSWORD ?= devpassword
TEST_DB_NAME ?= movie_finder_test
TEST_DATABASE_URL ?= postgresql://$(DB_USER):$(DB_PASSWORD)@postgres:5432/$(TEST_DB_NAME)

# Coverage artifacts are written into the bind-mounted workspace so VS Code
# extensions such as Coverage Gutters can visualize them from the host.
APP_PATHS := app/src app/tests
COVERAGE_XML ?= app-coverage.xml
COVERAGE_HTML ?= htmlcov/app
JUNIT_XML ?= test-results/junit.xml

help:
	@echo ""
	@echo "Movie Finder Backend — available targets"
	@echo "========================================="
	@echo ""
	@echo "  Editor"
	@echo "    editor-up      Start only the backend container for editing/linting"
	@echo "    editor-down    Stop the backend container and remove compose resources"
	@echo "    shell          Open a shell in the backend container"
	@echo ""
	@echo "  Lifecycle"
	@echo "    init           Pull postgres and build the backend dev image"
	@echo "    up             Start full stack (postgres + backend) in the background"
	@echo "    down           Stop the local backend stack and remove containers"
	@echo "    logs           Follow backend + postgres logs"
	@echo "    ci-down        Full cleanup for CI: stop containers and remove volumes + local images"
	@echo ""
	@echo "  Quality"
	@echo "    lint           Run ruff check for app/ inside Docker"
	@echo "    format         Run ruff format for app/ inside Docker"
	@echo "    typecheck      Run mypy --strict for app/ inside Docker"
	@echo "    test           Run pytest for app/ inside Docker"
	@echo "    test-coverage  Run pytest with coverage XML/HTML output"
	@echo "    detect-secrets Run detect-secrets inside Docker"
	@echo "    pre-commit     Run pre-commit hooks inside Docker"
	@echo "    check          Convenience alias: lint + typecheck + test (requires Docker)"
	@echo ""
	@echo "  Compatibility aliases"
	@echo "    build          Alias for init"
	@echo "    run            Alias for up"
	@echo "    run-dev        Alias for up"
	@echo "    setup          Alias for init"
	@echo ""

init:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) pull postgres
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) build $(SERVICE)

editor-up:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) up -d $(SERVICE)

editor-down:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) down --remove-orphans

ci-down:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) down -v --rmi local --remove-orphans

up:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) up --build -d

down:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) down --remove-orphans

logs:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) logs -f $(SERVICE) postgres

shell:
	@if BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) ps --services --status running | grep -qx "$(SERVICE)"; then \
		BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) exec $(SERVICE) sh; \
	else \
		BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) run --rm $(SERVICE) sh; \
	fi

lint:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) run --rm --no-deps $(SERVICE) ruff check $(APP_PATHS)

format:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) run --rm --no-deps $(SERVICE) ruff format $(APP_PATHS)

typecheck:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) run --rm --no-deps $(SERVICE) mypy app/src

test:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) run --rm -e DATABASE_URL="$(TEST_DATABASE_URL)" $(SERVICE) \
		pytest app/tests/ --asyncio-mode=auto -v --tb=short

test-coverage:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) run --rm -e DATABASE_URL="$(TEST_DATABASE_URL)" $(SERVICE) \
		pytest app/tests/ --asyncio-mode=auto -v --tb=short \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=xml:$(COVERAGE_XML) \
		--cov-report=html:$(COVERAGE_HTML) \
		--junitxml=$(JUNIT_XML)

detect-secrets:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) run --rm --no-deps $(SERVICE) detect-secrets scan --baseline .secrets.baseline # pragma: allowlist secret

pre-commit:
	BACKEND_GIT_DIR="$(GIT_DIR_HOST)" $(COMPOSE) run --rm --no-deps \
		$(SERVICE) pre-commit run --all-files

build: init

run: up

run-dev: up

setup: init

check: lint typecheck test
