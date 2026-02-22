# syntax=docker/dockerfile:1
ARG CUDA_VERSION=12.4.1
ARG PYTHON_VERSION=3.11

FROM nvidia/cuda:${CUDA_VERSION}-devel-ubuntu22.04 AS builder
ARG PYTHON_VERSION

# UV bináris átvétele
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON=python${PYTHON_VERSION}

WORKDIR /app

# Rendszerfüggőségek
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ninja-build && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Csak a konfigurációt másoljuk először a cache hatékonyság miatt
COPY pyproject.toml uv.lock ./

# Deps telepítése a lock alapján
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# flash-attn: nincs PyPI wheel, prebuilt wheel kell (torch a build-jéhez)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-cache \
    https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.7.16/flash_attn-2.6.3%2Bcu124torch2.6-cp311-cp311-linux_x86_64.whl

# Kód másolása és projekt regisztrálása
COPY src/ ./src/
COPY server.py ./
RUN touch README.md
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Tisztítás a venv-en belül
RUN find .venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    rm -rf .venv/lib/python3.11/site-packages/nvidia/nvtx && \
    rm -rf .venv/lib/python3.11/site-packages/nvidia/nccl

############################
# Stage 2: Runtime
############################
FROM nvidia/cuda:${CUDA_VERSION}-runtime-ubuntu22.04 AS runtime

ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" HF_HOME=/models

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3 curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy uv-managed Python (venv symlinks point here)
COPY --from=builder /root/.local/share/uv/python /root/.local/share/uv/python
# Csak a kész venv és a kód átmásolása
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/server.py /app/server.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["sh", "-c", "python3 -m gunicorn server:app --workers ${WORKERS:-1} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 600"]
