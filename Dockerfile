# =============================================================================
# movie-finder backend — FastAPI application Dockerfile
#
# Status: PLACEHOLDER — app/ is not yet implemented.
# This file will be completed when the FastAPI layer is built.
#
# Planned build context: backend/  (workspace root)
# The workspace members (chain, imdbapi) are installed together.
# =============================================================================

# ---- Stage 1: builder -------------------------------------------------------
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# TODO: Copy workspace pyproject + lock file + all workspace members
# COPY pyproject.toml uv.lock ./
# COPY chain/ ./chain/
# COPY imdbapi/ ./imdbapi/
# COPY app/ ./app/
# RUN --mount=type=cache,target=/root/.cache/uv \
#     uv sync --frozen --no-dev --all-packages

# ---- Stage 2: runtime -------------------------------------------------------
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="movie-finder-backend"
LABEL org.opencontainers.image.description="Movie Finder — FastAPI application (placeholder)"

RUN useradd --system --uid 1001 --no-create-home appuser

WORKDIR /app

# TODO: Copy venv and app source once app/ is implemented
# COPY --from=builder /build/.venv /app/.venv
# COPY app/src/ src/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# TODO: Replace with: CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EXPOSE 8000
CMD ["python", "-c", "print('FastAPI app not yet implemented. See app/README.md.')"]
