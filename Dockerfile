# Base image
ARG BASE_IMAGE=ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Stage 1: Install dependencies (cached layer - rarely changes)
FROM ${BASE_IMAGE} AS deps
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git poppler-utils && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first for better caching
COPY pyproject.toml uv.lock ./
RUN touch README.md && uv sync --frozen --no-install-project --no-dev --no-cache

ENV PATH="/app/.venv/bin:$PATH"

# Stage 2: Build the application (includes app code)
FROM deps AS builder
COPY src/ ./src/
COPY server.py prompts/ ./
RUN uv sync --frozen --no-dev --no-cache

# Stage 3: Runtime image
FROM builder AS runtime

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/server.py /app/server.py
COPY --from=builder /app/prompts /app/prompts

ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/src"
# Note: For GPU workloads, stick to 1 worker per GPU since each worker loads its own model copy (~8GB).
# Use WORKERS env var to configure worker count (default: 1)
CMD ["sh", "-c", "gunicorn server:app --workers ${WORKERS:-1} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 600"]
