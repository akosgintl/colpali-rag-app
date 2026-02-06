# CPU-only Dockerfile for Document API
# Image size: ~500MB (no PyTorch/CUDA, just FastAPI + dependencies)

FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Install poppler for pdf2image and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:/app/.venv/bin:$PATH"

# Copy dependency files
COPY pyproject.toml uv.lock ./
RUN touch README.md && uv sync --frozen --no-install-project --no-dev --no-cache

# Copy application
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY server.py ./
RUN uv sync --frozen --no-dev --no-cache


# Runtime stage
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install poppler for pdf2image and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/prompts /app/prompts/
COPY --from=builder /app/server.py /app/server.py

ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/src"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with multiple workers (CPU-only, can scale)
CMD ["sh", "-c", "gunicorn server:app --workers ${WORKERS:-4} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 600"]
