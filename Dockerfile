FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv globally
RUN pip install uv

# Copy only project config first to cache dependencies
COPY pyproject.toml uv.lock ./

# Ensure dev and rag dependency groups meant for scripts/tests are excluded in production container build 
RUN uv sync --no-dev --no-group rag || uv sync --no-dev

# Copy application source code
COPY . /app

# --- Production Stage ---
FROM builder AS production

# Non-root user for security compliance
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

EXPOSE 8000

# Execute server via uv run wrapper
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
