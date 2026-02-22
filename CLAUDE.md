# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

ColPali RAG App is a document retrieval system using Vision Language Models (VLMs). The application is split into three microservices:

1. **colpali-vlm/** - GPU-based VLM embedding service (RunPod deployment)
2. **multimodal_lm/** - GPU-based multimodal LM service running Qwen3-VL-32B-Instruct via vLLM (RunPod deployment)
3. **document-api/** - CPU-based API orchestration service (local/cloud deployment)

The system uses ColPali models (ColQwen2.5, ColQwen3, or TomoroAI ColQwen3) to generate embeddings directly from document images, preserving visual elements like tables and figures. Qdrant handles vector search, Supabase stores images, and Qwen3-VL-32B-Instruct (served via vLLM) generates responses.

## Project Structure

```
colpali-rag-app/
├── colpali-vlm/                        # VLM microservice (GPU)
│   ├── src/vlm/
│   │   ├── api/
│   │   │   ├── endpoints/embed.py      # /embed/images, /embed/query
│   │   │   ├── lifespan.py             # Model loading
│   │   │   ├── dependencies.py         # FastAPI DI
│   │   │   └── auth.py                 # JWT authentication
│   │   ├── colpali/loaders.py          # Multi-model loader factory
│   │   ├── logging_config.py
│   │   └── settings.py
│   ├── server.py
│   ├── pyproject.toml
│   ├── entrypoint.sh                   # Entrypoint: downloads model at container start
│   ├── Dockerfile                      # CUDA 12.4 + stripped deps, entrypoint model download
│   └── Makefile
│
├── multimodal_lm/                      # Multimodal LM microservice (GPU)
│   ├── Dockerfile                      # vLLM-OpenAI base image
│   ├── entrypoint.sh                   # Downloads model at container start
│   ├── Makefile
│   └── .env.example
│
├── document-api/                       # Document API microservice (CPU)
│   ├── src/doc_api/
│   │   ├── api/
│   │   │   ├── endpoints/
│   │   │   │   ├── pdf_ingest.py       # PDF ingestion
│   │   │   │   └── query.py            # Document query
│   │   │   ├── lifespan.py             # Client initialization
│   │   │   ├── dependencies.py         # FastAPI DI
│   │   │   ├── auth.py                 # JWT authentication
│   │   │   ├── state.py                # Client factories
│   │   │   ├── middleware.py            # Timeout middleware
│   │   │   └── rate_limit.py           # Rate limiting
│   │   ├── services/
│   │   │   ├── vlm_client.py           # HTTP client for VLM service
│   │   │   ├── img_uploader.py
│   │   │   └── img_downloader.py
│   │   ├── utils/
│   │   │   ├── prompt_utils.py
│   │   │   └── qdrant_utils.py
│   │   ├── logging_config.py
│   │   └── settings.py
│   ├── server.py
│   ├── pyproject.toml
│   ├── Dockerfile                      # CPU-only, lightweight (~500MB)
│   ├── Makefile
│   └── prompts/
│       ├── response_1
│       └── response_2
│
├── docker-compose.yml                  # Dev: all services (VLM + MLM + API)
├── docker-compose.runpod.yml           # Cloud: API only (VLM and MLM deployed separately)
└── Makefile                            # Root-level commands
```

## Docker Images

### VLM Service: `colpali-vlm/Dockerfile`
- **Use case**: All environments (development and production)
- **Model loading**: Entrypoint downloads model before app starts (`entrypoint.sh`)
- **Storage**: Models cached in Docker volume (`vlm_hf_cache` mounted at `/models`)
- **Model selection**: Via `.env` var `COLPALI_MODEL_NAME` (read by entrypoint + app)
- **Base**: CUDA 12.4 + Ubuntu 22.04 + prebuilt flash-attn wheel
- **Optimizations**: Multi-stage build with stripped site-packages (no NCCL, Triton, static libs)
- **Cons**: First startup takes 5-10 minutes for model download (cached after first run)
- **Usage**: `make docker_up` (default in `docker-compose.yml`)

### Multimodal LM Service: `multimodal_lm/Dockerfile`
- **Use case**: All environments (GPU required)
- **Model loading**: Entrypoint downloads model before vLLM starts (`entrypoint.sh`)
- **Storage**: Models cached in Docker volume (`mlm_hf_cache` mounted at `/models`)
- **Base**: `vllm/vllm-openai:latest`
- **API**: OpenAI-compatible `/v1/chat/completions` endpoint
- **Model**: Qwen3-VL-32B-Instruct (configurable via `MULTIMODAL_LM_MODEL_NAME`)
- **Cons**: First startup takes 10-15 minutes for large model download (~60GB, cached after first run)
- **Usage**: `make docker_up` or `cd multimodal_lm && make docker_build && make docker_run`

### Document API: `document-api/Dockerfile`
- **Use case**: All environments (CPU-only, ~500MB)
- **Base**: Python 3.12-slim
- **Usage**: `make docker_build_api`

## Commands

### Development (Local)
```bash
# Start VLM service (terminal 1, requires GPU)
make dev_vlm                    # Runs on port 8001

# Start API service (terminal 2)
make dev_api                    # Runs on port 8000, connects to VLM on 8001

# Or use docker-compose for both
make docker_up                  # Build and start both services
make docker_up_detach           # Run in background
make docker_logs                # View logs
make docker_down                # Stop services
```

### Cloud Deployment (API only, VLM and MLM deployed separately)
```bash
make docker_runpod_up           # Start API service only (VLM and MLM on remote GPUs)
make docker_runpod_up_detach    # Run in background
make docker_runpod_logs         # View logs
make docker_runpod_down         # Stop service
```

### Build & Push Images
```bash
make docker_build_vlm           # Build VLM image
make docker_push_vlm            # Push VLM to Docker Hub
make docker_build_mlm           # Build Multimodal LM image
make docker_push_mlm            # Push MLM to Docker Hub
make docker_build_api           # Build Document API image
make docker_push_api            # Push API to Docker Hub
make docker_build_all           # Build all three images
make docker_push_all            # Push all three images
```

### Code Quality
```bash
make pretty                     # Run lint + format + imports on both services
make mypy                       # Type checking
make all                        # All checks + cleanup
```

## Architecture

### VLM Service Endpoints

**POST /embed/images**
- Input: `multipart/form-data` with `images[]` (JPEG/PNG files)
- Output: `{"embeddings": [[[float, ...], ...], ...], "processing_time_ms": float}`
- Returns multi-vectors for each image (128-dim for ColQwen2.5, 320-dim for ColQwen3/TomoroAI)
- Embeddings are float16 values; responses are GZip-compressed

**POST /embed/query**
- Input: `{"query": "string"}`
- Output: `{"embedding": [[float, ...]], "processing_time_ms": float}`
- Returns multi-vector for query (128-dim for ColQwen2.5, 320-dim for ColQwen3/TomoroAI)
- Embedding is float16 values; response is GZip-compressed

**GET /health**
- Output: `{"status": "healthy", "model_loaded": true}`
- Returns 503 if model not yet loaded: `{"status": "unhealthy", "model_loaded": false}`

**GET /health/detailed**
- Output: `{"status": "healthy", "model_loaded": true, "device": "cuda", "model_name": "vidore/colqwen2.5-v0.2"}`

### Document API Flow

**Ingestion (`POST /ingest-pdfs/`):**
1. PDFs converted to JPEGs (300 DPI)
2. Images sent to VLM service for embeddings
3. Images uploaded to Supabase storage
4. Embeddings stored in Qdrant with session_id filter

**Query (`POST /query/`):**
1. Query sent to VLM service for embedding
2. Qdrant searches for similar pages (filtered by session_id)
3. Images downloaded from Supabase
4. Images + prompts sent to Qwen3-VL-32B-Instruct (via multimodal LM service, OpenAI-compatible API)
5. Response streamed back to client as Server-Sent Events

### Qdrant Collection Schema

Multi-vector configuration with:
- Vector size: 128 (ColQwen2.5) or 320 (ColQwen3/TomoroAI)
- Distance: Cosine with MaxSim comparator
- Indexed field: `session_id` (keyword type for filtering)

Payload structure: `{session_id, document, page}`

## Supported Models

The VLM service supports three model types:

1. **ColQwen2.5** (default): `vidore/colqwen2.5-v0.2`
   - Library: `colpali_engine`
   - Dimensions: 128
   - Best for: Standard document retrieval

2. **ColQwen3**: Various ColQwen3 models via `colpali_engine`
   - Library: `colpali_engine`
   - Dimensions: 320
   - Best for: Enhanced performance

3. **TomoroAI ColQwen3**: `TomoroAI/tomoro-colqwen3-embed-4b`
   - Library: `transformers`
   - Dimensions: 320
   - Best for: SOTA performance, smaller storage footprint (13× vs full-dim models)
   - Bonus: Video retrieval capability

### Switching Models

To switch to TomoroAI model:

1. Update `colpali-vlm/.env`:
   ```bash
   COLPALI_MODEL_NAME=TomoroAI/tomoro-colqwen3-embed-4b
   COLPALI_MODEL_TYPE=auto
   COLPALI_VECTOR_DIM=320
   ```

2. Update `document-api/.env`:
   ```bash
   VECTOR_DIM=320
   ```

3. Recreate Qdrant collection (vector dimensions must match)
4. Re-ingest all documents

## Environment Variables

### colpali-vlm/.env
```
# Model
COLPALI_MODEL_NAME=vidore/colqwen2.5-v0.2
COLPALI_MODEL_TYPE=auto                     # auto | colqwen2.5 | colqwen3 | tomoro-colqwen3
COLPALI_VECTOR_DIM=128                      # 128 for ColQwen2.5, 320 for ColQwen3/TomoroAI
MAX_CONCURRENT_INFERENCES=1

# Timeouts
INFERENCE_TIMEOUT_SECONDS=60

# Server
WORKERS=1
HOST=0.0.0.0
PORT=8000

# Authentication (optional)
AUTH_ENABLED=false
SUPABASE_URL=...                            # Required if AUTH_ENABLED=true
SUPABASE_KEY=...
SUPABASE_JWT_SECRET=...
```

### multimodal_lm/.env
```
# Model
MULTIMODAL_LM_MODEL_NAME=Qwen/Qwen3-VL-32B-Instruct
MULTIMODAL_LM_MAX_MODEL_LEN=16384          # Max context length
MULTIMODAL_LM_TENSOR_PARALLEL=1            # GPU parallelism (1 for single GPU, 2+ for multi-GPU)
MULTIMODAL_LM_GPU_MEMORY_UTIL=0.90         # GPU memory utilization (0.0-1.0)

# Server
PORT=8000
```

### document-api/.env
```
# VLM Service
VLM_SERVICE_URL=http://localhost:8001       # or RunPod URL
VLM_TIMEOUT_SECONDS=120                    # .env default; code fallback is 480

# Qdrant
QDRANT_URL=...
QDRANT_API_KEY=...
COLLECTION_NAME=...
VECTOR_DIM=128                              # Must match VLM: 128 for ColQwen2.5, 320 for ColQwen3/TomoroAI

# Supabase
SUPABASE_URL=...
SUPABASE_KEY=...
SUPABASE_JWT_SECRET=...                     # Required if AUTH_ENABLED=true
BUCKET=colpali

# Multimodal LM Service
MULTIMODAL_LM_SERVICE_URL=http://localhost:8002  # or RunPod URL
MULTIMODAL_LM_MODEL_NAME=Qwen/Qwen3-VL-32B-Instruct
MULTIMODAL_LM_MAX_TOKENS=8192
MULTIMODAL_LM_TEMPERATURE=0.0

# Authentication
AUTH_ENABLED=true
ALLOWED_ORIGINS=["*"]

# Processing Limits
MAX_FILE_SIZE_MB=50
MAX_TOTAL_UPLOAD_MB=200
MAX_PAGES_PER_BATCH=5
MAX_PDF_PAGES=200

# Rate Limiting
QUERY_RATE_LIMIT=30/minute
INGEST_RATE_LIMIT=10/minute

# Endpoint Timeouts
INGEST_ENDPOINT_TIMEOUT_SECONDS=600
QUERY_ENDPOINT_TIMEOUT_SECONDS=180

# Integration Timeouts
QDRANT_TIMEOUT_SECONDS=60
SUPABASE_TIMEOUT_SECONDS=120
MULTIMODAL_LM_TIMEOUT_SECONDS=180
PDF_CONVERSION_TIMEOUT_SECONDS=120

# Server
WORKERS=1
HOST=0.0.0.0
PORT=8000
```

## Production Features

### Authentication
- JWT-based authentication via Supabase tokens
- Configurable via `AUTH_ENABLED` and `SUPABASE_JWT_SECRET`
- Implemented in `document-api/src/doc_api/api/auth.py`

### Rate Limiting
- Endpoint-specific rate limits using slowapi
- `/query/`: 30 requests/minute
- `/ingest-pdfs/`: 10 requests/minute
- Implemented in `document-api/src/doc_api/api/rate_limit.py`

### Request Timeouts
- Global timeout middleware (default: 600s for ingest, 180s for query)
- Returns 504 Gateway Timeout on expiration
- Implemented in `document-api/src/doc_api/api/middleware.py`

### Concurrency Control
- VLM service: Model semaphore prevents concurrent GPU access (configurable via `MAX_CONCURRENT_INFERENCES`)
- Document API: Qdrant semaphore prevents connection pool exhaustion

### Memory Management
- Batch processing with configurable batch size
- Automatic CUDA cache clearing (VLM service)
- File size and page count limits

## Key Differences from Monolith

1. **VLM Service**: Separate GPU service handles all embedding inference
2. **Multimodal LM Service**: Separate GPU service handles response generation via vLLM (OpenAI-compatible API)
3. **VLM Client**: Document API uses `VLMClient` (httpx + tenacity) instead of direct model calls
4. **OpenAI Client**: Document API uses `AsyncOpenAI` to communicate with the multimodal LM service
5. **No colpali-engine or Anthropic**: Document API has no PyTorch/GPU/Anthropic dependencies
6. **Independent scaling**: API can scale horizontally; VLM and MLM scale per GPU
7. **Three Dockerfiles**: VLM (CUDA 12.4), MLM (vLLM-OpenAI), API (CPU-only ~500MB)
