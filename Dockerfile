# =============================================================================
# movie-finder-backend — FastAPI application images
#
# Build context: backend/ (workspace root)
#
# Targets:
#   dev      Local Docker-only development image used by docker-compose.yml
#   runtime  Production image used by Jenkins and Azure Container Apps
#
# Iteration boundary:
#   This Dockerfile supports the backend app stack only. `chain/` and `imdbapi/`
#   are available because the app imports them; `rag_ingestion/` keeps its own
#   repo-local environment and is intentionally excluded from the backend dev
#   image until the child issue lands.
# =============================================================================

FROM python:3.13-slim AS uv-base

# Pin uv to a minor series for reproducible local and CI images.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy


# ---- Stage 1: dev -----------------------------------------------------------
# Used by `docker-compose.yml` and VS Code "Attach to Running Container".
FROM uv-base AS dev

ARG WITH_PROVIDERS="default-cloud"

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    make \
    && rm -rf /var/lib/apt/lists/*

RUN git config --global --add safe.directory /workspace

WORKDIR /workspace

# Keep the interpreter in a stable location so VS Code launch/settings can
# point to `/opt/venv/bin/python` inside the attached container.
RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv" \
    PYTHONPATH="/workspace/app/src:/workspace/chain/src:/workspace/chain/imdbapi/src"

# Copy manifests and metadata only so Docker can cache the dependency layer aggressively.
# `--no-install-workspace` keeps the source tree out of the image because local
# development bind-mounts the live checkout into /workspace at runtime.
COPY pyproject.toml uv.lock README.md ./
COPY chain/pyproject.toml chain/README.md ./chain/
COPY chain/imdbapi/pyproject.toml chain/imdbapi/README.md ./chain/imdbapi/
COPY app/pyproject.toml app/README.md ./app/
COPY alembic.ini ./
COPY alembic ./alembic/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-packages --all-groups --extra "$WITH_PROVIDERS" --active --no-install-workspace

CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]


# ---- Stage 2: builder -------------------------------------------------------
FROM uv-base AS builder

ARG WITH_PROVIDERS="default-cloud"

WORKDIR /build

# Place the virtualenv at /app/.venv — the same absolute path used in the
# runtime stage. This ensures console-script shebangs (e.g. #!/app/.venv/bin/python3)
# remain valid after `COPY --from=builder /app/.venv /app/.venv`, so tools like
# `alembic` can be executed directly from PATH in the runtime container.
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# Copy workspace manifests and lock file first for layer caching.
COPY pyproject.toml uv.lock README.md ./
COPY chain/pyproject.toml chain/README.md ./chain/
COPY chain/imdbapi/pyproject.toml chain/imdbapi/README.md ./chain/imdbapi/
COPY app/pyproject.toml app/README.md ./app/
COPY alembic.ini ./
COPY alembic ./alembic/

# Install production dependencies for all workspace members into an isolated
# virtualenv. The runtime stage copies this venv directly.
# --no-install-workspace: install deps of all workspace members without trying
# to build the workspace packages themselves (source is not yet present).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-packages --extra "$WITH_PROVIDERS" --no-install-workspace

# Copy actual source and re-sync to install workspace packages as editable.
COPY chain/src ./chain/src
COPY chain/imdbapi/src ./chain/imdbapi/src
COPY app/src ./app/src
COPY scripts/start-backend.sh ./scripts/start-backend.sh

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-packages --extra "$WITH_PROVIDERS"


# ---- Stage 3: runtime -------------------------------------------------------
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="movie-finder-backend"
LABEL org.opencontainers.image.description="Movie Finder — FastAPI + LangGraph"

RUN useradd --system --uid 1001 --no-create-home appuser

# psycopg pure-Python fallback requires the libpq shared library.
# libpq-binary is not in the lock file (chain/pyproject.toml psycopg[binary]
# extra was added after uv lock was last run — regenerate uv.lock to fix that
# long-term). This ensures psycopg can connect to PostgreSQL via the python
# implementation until the lock file is refreshed.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the pre-built venv and source tree from the builder.
# `--link` creates independent layers that BuildKit can cache and resolve in
# parallel — safe to use with multi-stage copies.
COPY --link --from=builder /app/.venv /app/.venv
COPY --link --from=builder /build/app/src ./src
COPY --link --from=builder /build/chain/src ./chain_src
COPY --link --from=builder /build/chain/imdbapi/src ./imdbapi_src
COPY --link --from=builder /build/alembic.ini ./alembic.ini
COPY --link --from=builder /build/alembic ./alembic
COPY --link --from=builder /build/scripts/start-backend.sh ./start-backend.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src:/app/chain_src:/app/imdbapi_src"

RUN mkdir -p /app/logs && chown appuser /app/logs && chmod +x /app/start-backend.sh

USER appuser

EXPOSE 8000

# Liveness probe used by Docker, docker-compose, and Azure Container Apps.
# Uses stdlib urllib so the slim image does not need curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live', timeout=3)" \
    || exit 1

CMD ["/app/start-backend.sh", "python", "-m", "uvicorn", "app.main:app", \
    "--host", "0.0.0.0", "--port", "8000", \
    "--workers", "1"]
