# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

ColPali RAG App is a FastAPI backend for document retrieval using Vision Language Models (VLMs). It uses ColQwen 2.5 to index and retrieve information directly from document images, preserving visual elements like tables and figures. The app uses Qdrant for vector search, Supabase for image storage, and Claude Sonnet 4 for response generation.

## Commands

### Development
```bash
make dev                    # Start server with hot-reload (localhost:8000)
uv sync --all-groups        # Install dependencies
make create_collection      # Create empty Qdrant collection (required before first use)
```

### Code Quality
```bash
make pretty                 # Run lint + format + import sort
make mypy                   # Type checking
make all                    # Run all checks and clean caches
```

### Docker
```bash
make docker_build           # Build production image (~2.1GB)
make docker_run             # Run container (requires .env)
make docker_dev             # Run with docker-compose (hot-reload)
```

### RunPod (GPU Cloud)
```bash
make docker_build_runpod    # Build GPU image with CUDA + Flash Attention 2 + pre-downloaded model (~12GB)
make docker_push_runpod     # Push to Docker Hub (requires DOCKERHUB_USERNAME env var)
```

## Architecture

### Request Flow

**Ingestion (`POST /ingest-pdfs/`):**
1. PDFs converted to JPEGs (300 DPI) via pdf2image
2. Images uploaded to Supabase storage
3. ColQwen2.5 generates embeddings for each page
4. Embeddings stored in Qdrant with session_id filter

**Query (`POST /query/`):**
1. Query embedded using ColQwen2.5
2. Qdrant searches for similar pages (filtered by session_id)
3. Matching images downloaded from Supabase
4. Images + prompts sent to Claude Sonnet 4 via Instructor
5. Response streamed back to client

### Key Components

- **Lifespan (`src/app/api/lifespan.py`)**: Initializes all clients (Qdrant, Supabase, Anthropic) and loads the ColQwen2.5 model at startup. Shared state (including semaphores for concurrency control) accessed via FastAPI's `request.state`.

- **ColQwen2.5 Loader (`src/app/colpali/loaders.py`)**: Handles model loading with automatic device detection (CUDA/MPS/CPU) and Flash Attention 2 if available.

- **Dependencies (`src/app/api/dependencies.py`)**: FastAPI dependency injection for accessing shared state. Prompts are loaded once and cached.

- **Settings (`src/app/settings.py`)**: Pydantic settings loaded from `.env` file.

### Qdrant Collection Schema

Multi-vector configuration with:
- Vector size: 128 (ColQwen2.5 output dimension)
- Distance: Cosine with MaxSim comparator
- Indexed field: `session_id` (keyword type for filtering)

Payload structure: `{session_id, document, page}`

### Prompts

System prompts stored in `prompts/response_1` and `prompts/response_2`. These wrap the retrieved images when calling Claude.

## Environment Variables

Required in `.env`:
- `QDRANT_URL`, `QDRANT_API_KEY`, `COLLECTION_NAME`
- `SUPABASE_URL`, `SUPABASE_KEY`
- `ANTHROPIC_API_KEY`

Optional (with defaults):
- `SUPABASE_JWT_SECRET` - Required if `AUTH_ENABLED=true`
- `DEFAULT_MODEL` - LLM model (default: `claude-sonnet-4-20250514`)
- `AUTH_ENABLED` - Enable JWT authentication (default: `true`)
- `MAX_FILE_SIZE_MB` - Max file size (default: `50`)
- `MAX_CONCURRENT_INFERENCES` - Concurrency limit (default: `1`)
- `QUERY_RATE_LIMIT` - Rate limit for queries (default: `30/minute`)
- `INGEST_RATE_LIMIT` - Rate limit for ingestion (default: `10/minute`)

## Production Features

### Authentication
- JWT-based authentication via Supabase tokens
- Configurable via `AUTH_ENABLED` and `SUPABASE_JWT_SECRET`
- Implemented in `src/app/api/auth.py`

### Rate Limiting
- Endpoint-specific rate limits using slowapi
- `/query/`: 30 requests/minute
- `/ingest-pdfs/`: 10 requests/minute
- Implemented in `src/app/api/rate_limit.py`

### Request Timeouts
- Global timeout middleware (default: 300s)
- Returns 504 Gateway Timeout on expiration
- Implemented in `src/app/api/middleware.py`

### Concurrency Control
- Model semaphore prevents concurrent GPU access (configurable via `MAX_CONCURRENT_INFERENCES`)
- Qdrant semaphore prevents connection pool exhaustion (set to 3x model concurrency)

### Memory Management
- Batch processing with configurable batch size
- Automatic CUDA cache clearing
- File size and page count limits
