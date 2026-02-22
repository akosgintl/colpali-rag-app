# API Module

The API module is split across two services, each with their own endpoints, lifecycle management, and dependency injection.

## VLM Service API (`colpali-vlm/src/vlm/api/`)

```
src/vlm/api/
├── __init__.py
├── auth.py           # JWT authentication
├── lifespan.py       # Model loading lifecycle
├── dependencies.py   # FastAPI dependency injection
└── endpoints/
    └── embed.py      # /embed/images, /embed/query
```

### server.py (Entry Point)

```python
# colpali-vlm/server.py
app = FastAPI(
    title="ColPali VLM Service",
    description="Vision Language Model embedding service",
    lifespan=lifespan,
)
app.include_router(embed.router)
```

Health endpoints (`/health`, `/health/detailed`) are defined directly in `server.py`.

### lifespan.py - Model Loading

Loads the ColPali model and processor on startup using the `get_loader()` factory.

```python
class State(TypedDict):
    model: Any
    processor: Any
    model_semaphore: asyncio.Semaphore
    device: str
    model_name: str
    model_type: str
    settings: Any
```

The lifespan:
1. Loads settings
2. Creates loader via `get_loader(model_type, model_name)`
3. Loads model and processor
4. Creates model semaphore for concurrency control

### dependencies.py

| Function | Returns |
|----------|---------|
| `get_model` | Model instance |
| `get_processor` | Processor instance |
| `get_semaphore` | `asyncio.Semaphore` |
| `get_device` | Device string (cuda/mps/cpu) |
| `get_model_name` | Model name string |
| `get_settings_from_state` | `Settings` |

### auth.py

JWT authentication using Supabase tokens. Disabled by default (`AUTH_ENABLED=false`).

### endpoints/embed.py

**POST /embed/images**
- Accepts `list[UploadFile]` images
- Loads into PIL, processes through model
- Returns `EmbeddingResponse` with multi-vectors
- Protected by model semaphore and inference timeout

**POST /embed/query**
- Accepts `QueryEmbedRequest` with query string
- Processes through model (handles both `process_texts` and `process_queries` APIs)
- Returns `QueryEmbeddingResponse` with multi-vector

Both endpoints handle TomoroAI output format (`.embeddings` attribute) automatically.

---

## Document API (`document-api/src/doc_api/api/`)

```
src/doc_api/api/
├── __init__.py
├── auth.py           # JWT authentication
├── state.py          # Client factory functions
├── lifespan.py       # Client initialization lifecycle
├── dependencies.py   # FastAPI dependency injection
├── middleware.py      # Timeout middleware
├── rate_limit.py      # Rate limiting setup
└── endpoints/
    ├── __init__.py
    ├── pdf_ingest.py  # PDF ingestion endpoint
    └── query.py       # Query endpoint
```

### server.py (Entry Point)

```python
# document-api/server.py
app = FastAPI(
    title="Document API",
    description="Document ingestion and query API with VLM-powered retrieval",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(TimeoutMiddleware, endpoint_timeouts={...})
app.add_middleware(CORSMiddleware, allow_origins=settings.auth.allowed_origins, ...)
app.include_router(pdf_ingest.router)
app.include_router(query.router)
```

### state.py - Client Factories

Factory functions for creating async clients:

| Function | Returns | Description |
|----------|---------|-------------|
| `create_qdrant_client(settings)` | `AsyncQdrantClient` | With connection pooling (20 max, 10 keepalive) |
| `create_supabase_client(settings)` | `SupabaseAsyncClient` | With httpx timeout config |
| `create_openai_client(settings)` | `AsyncOpenAI (for multimodal LM)` | With httpx timeout config |

### lifespan.py - Client Initialization

```python
class State(TypedDict):
    vlm_client: VLMClient
    supabase_uploader: SupabaseJPEGUploader
    supabase_downloader: SupabaseJPEGDownloader
    openai_client: AsyncOpenAI
    qdrant_client: AsyncQdrantClient
    collection_name: str
    qdrant_semaphore: asyncio.Semaphore
    llm_config: dict[str, Any]
    settings: Any
```

The lifespan:
1. Creates `VLMClient` and waits for VLM service health (retry 30 attempts, exponential backoff 2-30s)
2. Waits for multimodal LM service health (retry 30 attempts, exponential backoff 2-30s)
3. Creates Qdrant, OpenAI (for multimodal LM), and Supabase clients
4. Creates uploader/downloader services
5. Creates Qdrant semaphore (10 concurrent)
6. Loads LLM config (model, max_tokens, temperature)

On shutdown: closes VLM client, Qdrant client, and OpenAI client.

### dependencies.py

| Function | Returns | Source |
|----------|---------|--------|
| `get_vlm_client` | `VLMClient` | `request.state.vlm_client` |
| `get_qdrant_client` | `AsyncQdrantClient` | `request.state.qdrant_client` |
| `get_supabase_uploader` | `SupabaseJPEGUploader` | `request.state.supabase_uploader` |
| `get_supabase_downloader` | `SupabaseJPEGDownloader` | `request.state.supabase_downloader` |
| `get_collection_name` | `str` | `request.state.collection_name` |
| `get_openai_client` | `AsyncOpenAI` | `request.state.openai_client` |
| `get_qdrant_semaphore` | `asyncio.Semaphore` | `request.state.qdrant_semaphore` |
| `get_llm_config` | `dict[str, Any]` | `request.state.llm_config` |
| `get_settings_from_state` | `Settings` | `request.state.settings` |
| `get_prompts` | `dict[str, str]` | Cached prompt file loading |
| `get_auth_token` | `str \| None` | Authorization header extraction |

### auth.py

JWT authentication using Supabase tokens. Enabled by default (`AUTH_ENABLED=true`).

`SupabaseAuthValidator` validates JWT structure, audience (`authenticated`), and expiration.

### middleware.py - TimeoutMiddleware

Applies per-endpoint timeouts:
- `/ingest-pdfs/`: 600s (default)
- `/query/`: 180s (default)
- Other endpoints: falls back to ingest timeout

Returns 504 Gateway Timeout when exceeded.

### rate_limit.py

Uses SlowAPI for per-IP rate limiting:
- `/query/`: 30 requests/minute
- `/ingest-pdfs/`: 10 requests/minute

### endpoints/pdf_ingest.py

`PDFIngestController` handles ingestion:
1. Reads PDF bytes, validates file size
2. Converts to JPEG via `pdf2image` (300 DPI, 4 threads)
3. Batches images (default: 5 per batch)
4. Calls `vlm_client.embed_images()` for each batch
5. Upserts to Qdrant via `upsert_with_retry()` (with vector_dim)
6. Uploads to Supabase via `uploader.upload_images()`

Auth token is forwarded to VLM service.

### endpoints/query.py

`QueryController` handles queries:
1. Calls `vlm_client.embed_query()` for query embedding
2. Searches Qdrant with session_id filter
3. Downloads images from Supabase as base64
4. Constructs OpenAI vision messages with images and system prompts
5. Streams response via `openai_client.chat.completions.create(stream=True)`
6. Returns Server-Sent Events with `data: [DONE]` terminator

Auth token is forwarded to VLM service.
