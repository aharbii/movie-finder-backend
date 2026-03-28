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
	pre-commit build run run-dev setup check

.DEFAULT_GOAL := help

COMPOSE ?= docker compose
SERVICE ?= backend

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

help:
	@echo ""
	@echo "Movie Finder Backend — available targets"
	@echo "========================================="
	@echo ""
	@echo "  Lifecycle"
	@echo "    init           Pull postgres and build the backend dev image"
	@echo "    up             Start postgres + backend in the background"
	@echo "    down           Stop the local backend stack and remove containers"
	@echo "    logs           Follow backend + postgres logs"
	@echo "    shell          Open a shell in the running backend container"
	@echo ""
	@echo "  Quality"
	@echo "    lint           Run ruff check for app/ inside Docker"
	@echo "    format         Run ruff format for app/ inside Docker"
	@echo "    typecheck      Run mypy --strict for app/ inside Docker"
	@echo "    test           Run pytest for app/ inside Docker"
	@echo "    test-coverage  Run pytest with coverage XML/HTML output"
	@echo "    pre-commit     Run pre-commit hooks inside Docker"
	@echo "    check          Convenience alias: lint + typecheck + test"
	@echo ""
	@echo "  Compatibility aliases"
	@echo "    build          Alias for init"
	@echo "    run            Alias for up"
	@echo "    run-dev        Alias for up"
	@echo "    setup          Alias for init"
	@echo ""

init:
	$(COMPOSE) pull postgres
	$(COMPOSE) build $(SERVICE)

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down --remove-orphans

logs:
	$(COMPOSE) logs -f $(SERVICE) postgres

shell:
	@if $(COMPOSE) ps --services --status running | grep -qx "$(SERVICE)"; then \
		$(COMPOSE) exec $(SERVICE) sh; \
	else \
		$(COMPOSE) run --rm $(SERVICE) sh; \
	fi

lint:
	$(COMPOSE) run --rm --no-deps $(SERVICE) ruff check $(APP_PATHS)

format:
	$(COMPOSE) run --rm --no-deps $(SERVICE) ruff format $(APP_PATHS)

typecheck:
	$(COMPOSE) run --rm --no-deps $(SERVICE) mypy app/src

test:
	$(COMPOSE) run --rm -e DATABASE_URL="$(TEST_DATABASE_URL)" $(SERVICE) \
		pytest app/tests/ --asyncio-mode=auto -v --tb=short

test-coverage:
	$(COMPOSE) run --rm -e DATABASE_URL="$(TEST_DATABASE_URL)" $(SERVICE) \
		pytest app/tests/ --asyncio-mode=auto -v --tb=short \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=xml:$(COVERAGE_XML) \
		--cov-report=html:$(COVERAGE_HTML)

pre-commit:
	$(COMPOSE) run --rm --no-deps $(SERVICE) pre-commit run --all-files

build: init

run: up

run-dev: up

setup: init

check: lint typecheck test
