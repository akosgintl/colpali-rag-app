<h1 align="center">ColPali RAG App</h1>
<div align="center">
    <a align="center" href="https://www.python.org/downloads/release/python-3110/"><img src="https://img.shields.io/badge/python-3.11%20%7C%203.12-red"/></a>
    <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.115.8-009688.svg?style=flat&logo=FastAPI&logoColor=white"/></a>
    <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json"/></a>
    <a href="http://mypy-lang.org/"><img src="http://www.mypy-lang.org/static/mypy_badge.svg"/></a>
    <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff" style="max-width:100%;"></a>
</div>

## Context
ColPali is a document retrieval method that leverages Vision Language Models (VLMs) to index and retrieve information directly from document images, bypassing traditional text extraction methods. By processing entire document pages as images, ColPali captures both textual content and visual elements—such as tables, figures, and layouts—thereby preserving the document's original structure and context.

![colpali](assets/colpali.png)

You can find more information about this method in the [ColPali paper](https://arxiv.org/abs/2407.01449). They also have a [ColPali repository](https://github.com/illuin-tech/colpali) with the code and models.

## Description
This repository contains the backend for a retrieval augmented generation (RAG) application that leverages the ColPali method. The application is split into **two microservices**:

1. **colpali-vlm/** - A GPU-based VLM embedding service that handles model inference. Supports multiple models: [ColQwen 2.5](https://huggingface.co/vidore/colqwen2.5-v0.2) (128-dim), ColQwen3 (320-dim), and [TomoroAI ColQwen3](https://huggingface.co/TomoroAI/tomoro-colqwen3-embed-4b) (320-dim).
2. **document-api/** - A CPU-based API orchestration service that handles PDF ingestion, querying, and response generation. Communicates with the VLM service over HTTP.

The system uses Qdrant for vector search, Supabase for image storage, and Claude Sonnet 4 for response generation.

### Ingestion
During the ingestion process, the Document API converts PDFs into JPEGs using **pdf2image**. These images are sent to the VLM service for embedding generation, then uploaded to Supabase storage and indexed in Qdrant.

![ingestion](assets/ingestion.png)

### Inference
At inference time, the query is sent to the VLM service for embedding, then Qdrant returns the top-k matching document pages (filtered by session_id). The Document API fetches the corresponding images from Supabase and sends them with the query to Claude Sonnet 4 for response generation.

![inference](assets/inference.png)

## Supported Models

| Model | Library | Dimensions | Best for |
|-------|---------|-----------|----------|
| **ColQwen2.5** (default) | `colpali_engine` | 128 | Standard document retrieval |
| **ColQwen3** | `colpali_engine` | 320 | Enhanced performance |
| **TomoroAI ColQwen3** | `transformers` | 320 | SOTA performance, smaller storage footprint |

## Stack

### VLM Service (`colpali-vlm/`)
* [PyTorch](https://pytorch.org/) + CUDA
* [colpali-engine](https://github.com/illuin-tech/colpali) (ColQwen2.5/ColQwen3)
* [transformers](https://huggingface.co/docs/transformers) (TomoroAI)
* [FastAPI](https://fastapi.tiangolo.com/)

### Document API (`document-api/`)
* [httpx](https://www.python-httpx.org/) + [tenacity](https://tenacity.readthedocs.io/) (VLM client with retry)
* [Instructor](https://python.useinstructor.com/) (structured LLM output)
* [Qdrant](https://qdrant.tech/) (vector search)
* [Supabase](https://supabase.com/) (image storage)
* [FastAPI](https://fastapi.tiangolo.com/)
* [PyJWT](https://pyjwt.readthedocs.io/) (authentication)
* [SlowAPI](https://github.com/laurentS/slowapi) (rate limiting)

### Common
* Programming Language: [Python 3.11](https://www.python.org/) (VLM) / [Python 3.12](https://www.python.org/) (Document API)
* Dependency & Package Manager: [uv](https://docs.astral.sh/uv/)
* Linters: [Ruff](https://docs.astral.sh/ruff/)
* Type Checking: [MyPy](https://mypy-lang.org/)
* Deployment: [Docker](https://www.docker.com/)

## Configure

1. **Clone the Git repository to your local machine:**
```shell
git clone https://github.com/jjovalle99/colpali-rag-app.git
cd colpali-rag-app
```

2. **Copy the `.env.example` files and replace placeholder values with the required credentials:**

```shell
# VLM service configuration
cp colpali-vlm/.env.example colpali-vlm/.env

# Document API configuration
cp document-api/.env.example document-api/.env
```

**VLM service variables (`colpali-vlm/.env`):**
```bash
# Model Configuration
COLPALI_MODEL_NAME=vidore/colqwen2.5-v0.2
COLPALI_MODEL_TYPE=auto
COLPALI_VECTOR_DIM=128

# Concurrency & Timeouts
MAX_CONCURRENT_INFERENCES=1
INFERENCE_TIMEOUT_SECONDS=60

# Server
WORKERS=1
HOST=0.0.0.0
PORT=8000

# Authentication (optional, disabled by default)
AUTH_ENABLED=false
```

**Document API variables (`document-api/.env`):**
```bash
# VLM Service Connection (Required)
VLM_SERVICE_URL=http://localhost:8001
VLM_TIMEOUT_SECONDS=120                # Timeout for VLM HTTP requests (code default: 480)

# Qdrant (Required)
QDRANT_URL=fillme
QDRANT_API_KEY=fillme
COLLECTION_NAME=fillme
VECTOR_DIM=128                  # Must match VLM: 128 for ColQwen2.5, 320 for ColQwen3/TomoroAI

# Supabase (Required)
SUPABASE_URL=fillme
SUPABASE_KEY=fillme
SUPABASE_JWT_SECRET=fillme      # Required if AUTH_ENABLED=true
BUCKET=colpali

# Anthropic (Required)
ANTHROPIC_API_KEY=fillme
DEFAULT_MODEL=claude-sonnet-4-20250514

# Optional
AUTH_ENABLED=true
MAX_FILE_SIZE_MB=50
QUERY_RATE_LIMIT=30/minute
INGEST_RATE_LIMIT=10/minute
```

## Installation and Usage

There are two ways to run the application: using Docker Compose or running both services locally.

### Using Docker Compose

1. **Ensure Docker is installed on your machine.** For more information, visit the official [Docker documentation](https://docs.docker.com/).

2. **Build and start both services:**

   ```shell
   make docker_up
   ```
   **Note**: On first startup, the VLM service will download the model (~4GB). Subsequent starts use the cached volume.

3. **Access the application docs:**
   - Document API: [http://localhost:8000/docs](http://localhost:8000/docs)
   - VLM Service: [http://localhost:8001/docs](http://localhost:8001/docs)

4. **View logs:**
   ```shell
   make docker_logs
   ```

5. **Stop both services:**
   ```shell
   make docker_down
   ```

### Running Locally

1. **Install `uv` by following the instructions** [here](https://docs.astral.sh/uv/getting-started/installation/).

2. **Install poppler-utils:**
```shell
sudo apt-get install poppler-utils
```

3. **Install dependencies for both services:**
```shell
cd colpali-vlm && uv sync && cd ..
cd document-api && uv sync && cd ..
```

4. **Start the VLM service (terminal 1, requires GPU):**
```shell
make dev_vlm    # Runs on port 8001
```

5. **Start the Document API (terminal 2):**
```shell
make dev_api    # Runs on port 8000, connects to VLM on 8001
```

6. **Access the application:**
   - Document API: [http://localhost:8000/docs](http://localhost:8000/docs)
   - VLM Service: [http://localhost:8001/docs](http://localhost:8001/docs)

## Docker Images

| Service | Dockerfile | Model Loading | Use Case |
|---------|-----------|---------------|----------|
| VLM Service | `colpali-vlm/Dockerfile` | Runtime download via entrypoint | All environments (CUDA 12.4, Python 3.11) |
| Document API | `document-api/Dockerfile` | N/A (CPU-only, ~500MB) | All environments (Python 3.12) |

The VLM image uses a multi-stage build (CUDA 12.4 + Ubuntu 22.04 + stripped deps) and downloads the model at container startup via `entrypoint.sh`. Models are cached in a Docker volume (`vlm_hf_cache`).

### Cloud Deployment (GPU)

1. **Build and push images:**
```shell
export DOCKERHUB_USERNAME=your-username
docker login
make docker_build_vlm && make docker_push_vlm
make docker_build_api && make docker_push_api
```

2. **Deploy** - See [docs/deployment.md](docs/deployment.md) for detailed instructions.

### Flash Attention 2 (Optional)

The VLM service automatically uses [Flash Attention 2](https://github.com/Dao-AILab/flash-attention) when available, which significantly speeds up model inference. Flash Attention only applies to the VLM service (GPU). If not installed, it falls back to standard attention.

**Requirements:**
- Linux (native or WSL2)
- NVIDIA GPU with compute capability >= 8.0 (RTX 30xx / Ampere series or newer)
- CUDA 12.4+

**Note for Windows users:** Flash Attention 2 is not supported on native Windows. To use it, run the application inside WSL2.

#### Installing on WSL2

1. **Verify GPU access in WSL2:**
   ```shell
   nvidia-smi
   ```

2. **Install build dependencies:**
   ```shell
   sudo apt install build-essential
   ```

3. **Install Flash Attention 2:**
   ```shell
   pip install flash-attn --no-build-isolation
   ```
   Note: Compilation takes 10-20 minutes.

4. **Verify installation:**
   ```python
   from transformers.utils.import_utils import is_flash_attn_2_available
   print(is_flash_attn_2_available())  # Should print True
   ```

If WSL2 runs out of memory during compilation or model loading, configure `.wslconfig` to allocate more RAM.

## Structure
```shell
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
│   ├── Dockerfile                      # CUDA 12.4 + stripped deps, entrypoint model download
│   ├── entrypoint.sh                   # Downloads model at container start
│   └── Makefile
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
│   │   ├── models/
│   │   │   └── query_response.py
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
├── docker-compose.yml                  # Dev: both services (VLM + API)
├── docker-compose.runpod.yml           # Cloud: API only (VLM deployed separately)
├── scripts/
│   └── get_token.py
└── Makefile                            # Root-level commands
```
