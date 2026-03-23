# =============================================================================
# movie-finder backend — FastAPI application
#
# Build context: backend/  (workspace root)
# All workspace members (chain, imdbapi, app) are installed together.
#
# Build:
#   docker build -t movie-finder-app .
# Run:
#   docker run --env-file .env -p 8000:8000 movie-finder-app
# =============================================================================

# ---- Stage 1: builder -------------------------------------------------------
FROM python:3.13-slim AS builder

# Pin uv to a minor-version series for reproducible builds.
# Bump this line when you want to upgrade uv.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /build

# Copy workspace manifests and lock file first for layer caching
COPY pyproject.toml uv.lock ./
COPY chain/pyproject.toml ./chain/
COPY imdbapi/pyproject.toml ./imdbapi/
COPY app/pyproject.toml ./app/

# Install all workspace packages (no dev deps) into an isolated venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-packages

# Copy actual source after deps are cached
COPY chain/src ./chain/src
COPY imdbapi/src ./imdbapi/src
COPY app/src ./app/src


# ---- Stage 2: runtime -------------------------------------------------------
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="movie-finder-backend"
LABEL org.opencontainers.image.description="Movie Finder — FastAPI + LangGraph"

RUN useradd --system --uid 1001 --no-create-home appuser

WORKDIR /app

# Copy only the pre-built venv and source tree from the builder.
# --link creates independent layers that BuildKit can cache and resolve in
# parallel — safe to use with multi-stage copies.
COPY --link --from=builder /build/.venv /app/.venv
COPY --link --from=builder /build/app/src ./src
COPY --link --from=builder /build/chain/src ./chain_src
COPY --link --from=builder /build/imdbapi/src ./imdbapi_src

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

USER appuser

EXPOSE 8000

# Liveness probe used by Docker, docker-compose, and Azure Container Apps.
# Uses stdlib urllib — no curl required in the slim image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" \
        || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1"]
