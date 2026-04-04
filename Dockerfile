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

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-packages --all-groups --active --no-install-workspace

CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]


# ---- Stage 2: builder -------------------------------------------------------
FROM uv-base AS builder

WORKDIR /build

# Copy workspace manifests and lock file first for layer caching.
COPY pyproject.toml uv.lock ./
COPY chain/pyproject.toml ./chain/
COPY chain/imdbapi/pyproject.toml ./chain/imdbapi/
COPY app/pyproject.toml ./app/

# Install production dependencies for all workspace members into an isolated
# virtualenv. The runtime stage copies this venv directly.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-packages

# Copy actual source after dependencies are cached.
COPY chain/src ./chain/src
COPY chain/imdbapi/src ./chain/imdbapi/src
COPY app/src ./app/src


# ---- Stage 3: runtime -------------------------------------------------------
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="movie-finder-backend"
LABEL org.opencontainers.image.description="Movie Finder — FastAPI + LangGraph"

RUN useradd --system --uid 1001 --no-create-home appuser

WORKDIR /app

# Copy only the pre-built venv and source tree from the builder.
# `--link` creates independent layers that BuildKit can cache and resolve in
# parallel — safe to use with multi-stage copies.
COPY --link --from=builder /build/.venv /app/.venv
COPY --link --from=builder /build/app/src ./src
COPY --link --from=builder /build/chain/src ./chain_src
COPY --link --from=builder /build/chain/imdbapi/src ./imdbapi_src

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src:/app/chain_src:/app/imdbapi_src"

RUN mkdir -p /app/logs && chown appuser /app/logs

USER appuser

EXPOSE 8000

# Liveness probe used by Docker, docker-compose, and Azure Container Apps.
# Uses stdlib urllib so the slim image does not need curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live', timeout=3)" \
    || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", \
    "--host", "0.0.0.0", "--port", "8000", \
    "--workers", "1"]
