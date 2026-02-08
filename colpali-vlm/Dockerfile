# Dockerfile.dbc - Optimized for Docker Build Cloud
# - No model baked into the image (download at runtime)
# - Slimmer Python deps copied into runtime instead of full .venv

ARG CUDA_VERSION=12.8.1

############################
# Stage 1: Build deps
############################
FROM nvidia/cuda:${CUDA_VERSION}-devel-ubuntu24.04 AS deps

ENV DEBIAN_FRONTEND=noninteractive
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Install Python & tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-dev \
    git \
    curl \
    ninja-build \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:/app/.venv/bin:$PATH"

# Copy dependency files
COPY pyproject.toml uv.lock ./
RUN touch README.md && \
    uv sync --frozen --no-install-project --no-dev --no-cache

# Install flash-attn from prebuilt wheel
RUN uv pip install --no-cache \
    https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.7.2/flash_attn-2.8.3%2Bcu128torch2.8-cp312-cp312-linux_x86_64.whl && \
    uv cache clean || true

# Extra packages (same as original)
RUN uv pip install --no-cache cffi auto-round>=0.5 && \
    uv cache clean || true

# Create a stripped deps dir (site-packages only, no venv metadata)
RUN mkdir -p /deps && \
    cp -a /app/.venv/lib/python3.12/site-packages/* /deps/ && \
    #
    # === Strip NVIDIA libs not needed for single-GPU inference ===
    # NCCL: multi-GPU communication only (~700MB) - not needed
    # cuSPARSELt: keep - PyTorch links against libcusparseLt.so.0 at import time
    # cuDNN: keep - PyTorch links against libcudnn.so.9 at import time
    # Remove all static libraries (.a) across nvidia packages - only .so needed at runtime
    find /deps/nvidia -type f -name "*.a" -delete 2>/dev/null || true && \
    # Remove NVTX (profiling only)
    rm -rf /deps/nvidia/nvtx /deps/nvidia_nvtx_cu12* && \
    #
    # === Strip other large unnecessary components ===
    # Triton: JIT kernel compiler (~500MB) - not needed with prebuilt flash-attn
    rm -rf /deps/triton /deps/triton-*.dist-info && \
    # Remove test directories and documentation
    find /deps -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /deps -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    #
    # === Clean Python caches ===
    find /deps -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /deps -type f -name "*.pyc" -delete || true && \
    find /deps -type f -name "*.pyo" -delete || true

############################
# Stage 2: Build application
############################
FROM deps AS builder

WORKDIR /app
COPY src/ ./src/
COPY server.py ./

# Sync project deps (no dev) into the same venv and then clean
RUN uv sync --frozen --no-dev --no-cache && \
    find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app -type f -name "*.pyc" -delete || true && \
    find /app -type f -name "*.pyo" -delete || true && \
    uv cache clean || true

############################
# Stage 3: Runtime (DBC)
############################
FROM nvidia/cuda:${CUDA_VERSION}-runtime-ubuntu24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
# Models will live here at runtime, not baked into the image
ENV HF_HOME=/models
ENV HF_HUB_ENABLE_HF_TRANSFER=0

WORKDIR /app

# Minimal runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy stripped Python deps and app code
COPY --from=deps /deps /usr/local/lib/python3.12/dist-packages
COPY --from=builder /app/src /app/src
COPY --from=builder /app/server.py /app/server.py

# Runtime-only Python path
ENV PYTHONPATH="/usr/local/lib/python3.12/dist-packages:/app/src"

# Entrypoint: download model at container start (runtime, not build)
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000

# Health check (same as original)
HEALTHCHECK --interval=30s --timeout=10s --start-period=600s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# One worker per GPU recommended
CMD ["sh", "-c", "python3 -m gunicorn server:app --workers ${WORKERS:-1} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 600"]
ENTRYPOINT ["/entrypoint.sh"]
