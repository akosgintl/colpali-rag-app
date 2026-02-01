# API Module

The API module contains the FastAPI application setup, endpoints, lifecycle management, and dependency injection.

## Module Structure

```
src/app/api/
├── __init__.py
├── auth.py           # JWT authentication
├── state.py          # Client factory functions
├── lifespan.py       # Application lifecycle manager
├── dependencies.py   # FastAPI dependency injection
├── middleware.py     # Timeout middleware
├── rate_limit.py     # Rate limiting setup
└── endpoints/
    ├── __init__.py
    ├── pdf_ingest.py # PDF ingestion endpoint
    └── query.py      # Query endpoint
```

## Component Diagram

```mermaid
graph TD
    subgraph api["api/"]
        state["state.py"]
        lifespan["lifespan.py"]
        deps["dependencies.py"]

        subgraph endpoints["endpoints/"]
            ingest["pdf_ingest.py"]
            query["query.py"]
        end
    end

    subgraph external["External Clients"]
        qdrant["Qdrant"]
        supabase["Supabase"]
        anthropic["Anthropic"]
    end

    state --> qdrant
    state --> supabase
    state --> anthropic
    lifespan --> state
    deps --> lifespan
    ingest --> deps
    query --> deps
```

---

## state.py - Client Factories

Factory functions for creating async clients.

### Functions

#### `create_qdrant_client(settings: Settings) -> AsyncQdrantClient`

Creates an async Qdrant client with connection pool configuration.

```python
def create_qdrant_client(settings: Settings) -> AsyncQdrantClient:
    # Configure httpx limits for connection pooling
    limits = httpx.Limits(
        max_connections=20,
        max_keepalive_connections=10,
    )

    return AsyncQdrantClient(
        url=settings.qdrant.qdrant_url,
        api_key=settings.qdrant.qdrant_api_key,
        timeout=settings.timeout.qdrant_timeout_seconds,
        limits=limits,
    )
```

**Parameters:**
- `settings`: Root Settings object

**Returns:** AsyncQdrantClient instance

---

#### `create_supabase_client(settings: Settings) -> SupabaseAsyncClient`

Creates a Supabase async client.

```python
def create_supabase_client(settings: Settings) -> SupabaseAsyncClient:
    return SupabaseAsyncClient(
        supabase_key=settings.supabase.supabase_key,
        supabase_url=settings.supabase.supabase_url,
    )
```

**Parameters:**
- `settings`: Root Settings object

**Returns:** Supabase AsyncClient instance

---

#### `create_anthropic_client(settings: Settings) -> AsyncAnthropic`

Creates an async Anthropic client with timeout configuration.

```python
def create_anthropic_client(settings: Settings) -> AsyncAnthropic:
    # Configure httpx client with timeout
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(float(settings.timeout.anthropic_timeout_seconds)),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )

    return AsyncAnthropic(
        api_key=settings.anthropic.anthropic_api_key,
        http_client=http_client,
    )
```

**Parameters:**
- `settings`: Root Settings object

**Returns:** AsyncAnthropic instance

---

## lifespan.py - Lifecycle Manager

Manages application startup and shutdown.

### State TypedDict

```python
class State(TypedDict):
    model: ColQwen2_5
    processor: ColQwen2_5_Processor
    supabase_uploader: SupabaseJPEGUploader
    supabase_downloader: SupabaseJPEGDownloader
    instructor_client: AsyncInstructor
    qdrant_client: AsyncQdrantClient
    collection_name: str
    model_semaphore: asyncio.Semaphore   # Concurrency control for GPU
    qdrant_semaphore: asyncio.Semaphore  # Concurrency control for Qdrant
    llm_config: dict[str, Any]           # LLM configuration
    settings: Settings                    # Application settings
```

### Lifecycle Flow

```mermaid
sequenceDiagram
    participant App as FastAPI
    participant Life as lifespan()
    participant Clients as Clients
    participant Model as ColQwen2.5

    Note over Life: Startup Phase

    Life->>Life: Load settings
    Life->>Clients: Create Qdrant client
    Life->>Clients: Create Anthropic client
    Life->>Clients: Create Supabase client
    Life->>Life: Wrap with Instructor
    Life->>Life: Create uploader/downloader
    Life->>Model: Load model & processor

    Life->>App: yield State

    Note over Life: Running Phase
    App->>App: Handle requests

    Note over Life: Shutdown Phase
    Life->>Clients: Close Qdrant client
    Life->>Clients: Close Anthropic client
```

### Function

#### `lifespan(app: FastAPI) -> AsyncGenerator[State, None]`

Async context manager for application lifecycle.

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[State, None]:
    # Startup
    settings = get_settings()
    qdrant_client = create_qdrant_client(settings.qdrant)
    anthropic_client = create_anthropic_client(settings.anthropic)
    supabase_client = await create_supabase_client(settings.supabase)

    instructor_client = instructor.from_anthropic(anthropic_client)

    uploader = SupabaseJPEGUploader(supabase_client, settings.supabase.bucket)
    downloader = SupabaseJPEGDownloader(supabase_client, settings.supabase.bucket)

    loader = ColQwen2_5Loader(settings.colpali.colpali_model_name)
    model, processor = loader.load()

    yield {
        "model": model,
        "processor": processor,
        "supabase_uploader": uploader,
        "supabase_downloader": downloader,
        "instructor_client": instructor_client,
        "qdrant_client": qdrant_client,
        "collection_name": settings.qdrant.collection_name,
    }

    # Shutdown
    await qdrant_client.close()
    await anthropic_client.close()
```

---

## dependencies.py - Dependency Injection

FastAPI dependency functions for accessing shared state.

### Dependency Flow

```mermaid
graph LR
    subgraph Request["Request"]
        R["request.state"]
    end

    subgraph Dependencies["Dependencies"]
        D1["get_qdrant_client"]
        D2["get_colpali_model"]
        D3["get_colpali_processor"]
        D4["get_supabase_uploader"]
        D5["get_supabase_downloader"]
        D6["get_collection_name"]
        D7["get_instructor_client"]
        D8["get_prompts"]
    end

    R --> D1
    R --> D2
    R --> D3
    R --> D4
    R --> D5
    R --> D6
    R --> D7
```

### Functions

All dependency functions follow the same pattern:

```python
async def get_qdrant_client(request: Request) -> AsyncQdrantClient:
    return request.state.qdrant_client
```

| Function | Returns | Source |
|----------|---------|--------|
| `get_qdrant_client` | `AsyncQdrantClient` | `request.state.qdrant_client` |
| `get_colpali_model` | `ColQwen2_5` | `request.state.model` |
| `get_colpali_processor` | `ColQwen2_5_Processor` | `request.state.processor` |
| `get_supabase_uploader` | `SupabaseJPEGUploader` | `request.state.supabase_uploader` |
| `get_supabase_downloader` | `SupabaseJPEGDownloader` | `request.state.supabase_downloader` |
| `get_collection_name` | `str` | `request.state.collection_name` |
| `get_instructor_client` | `AsyncInstructor` | `request.state.instructor_client` |
| `get_model_semaphore` | `asyncio.Semaphore` | `request.state.model_semaphore` |
| `get_qdrant_semaphore` | `asyncio.Semaphore` | `request.state.qdrant_semaphore` |
| `get_llm_config` | `dict[str, Any]` | `request.state.llm_config` |
| `get_settings_from_state` | `Settings` | `request.state.settings` |
| `get_current_user` | `dict \| None` | JWT token validation |

### Cached Dependency

#### `get_prompts() -> dict[str, str]`

Loads prompts from files (cached with `@lru_cache`).

```python
@lru_cache(maxsize=1)
def get_prompts():
    logger.info("Loading prompts (cached)")
    prompt1 = read_prompt_from_plain_file("prompts/response_1")
    prompt2 = read_prompt_from_plain_file("prompts/response_2")
    return {"prompt1": prompt1, "prompt2": prompt2}
```

**Returns:** Dict with `prompt1` and `prompt2` keys

---

## endpoints/pdf_ingest.py - Ingestion Endpoint

Handles PDF document ingestion.

### PDFIngestController

Controller class encapsulating ingestion logic.

```mermaid
classDiagram
    class PDFIngestController {
        -model: ColQwen2_5
        -processor: ColQwen2_5_Processor
        -qdrant_client: AsyncQdrantClient
        -collection_name: str
        -supabase_uploader: SupabaseJPEGUploader
        -batch_size: int

        +ingest(files, session_id) IngestResponse
        -_convert_pdf_to_images(file) List[Image]
        -_process_images_batch(images, session_id, filename) None
    }
```

### Endpoint

#### `POST /ingest-pdfs/`

```python
@router.post("/ingest-pdfs/")
async def ingest_pdfs(
    files: list[UploadFile] = File(...),
    session_id: UUID4 = Form(...),
    model: ColQwen2_5 = Depends(get_colpali_model),
    processor: ColQwen2_5_Processor = Depends(get_colpali_processor),
    qdrant_client: AsyncQdrantClient = Depends(get_qdrant_client),
    collection_name: str = Depends(get_collection_name),
    supabase_uploader: SupabaseJPEGUploader = Depends(get_supabase_uploader),
) -> IngestResponse:
```

### Processing Pipeline

```mermaid
sequenceDiagram
    participant Controller
    participant PDF as pdf2image
    participant Model as ColQwen2.5
    participant Qdrant
    participant Supabase

    Controller->>PDF: convert_from_bytes(300 DPI, 4 threads)
    PDF-->>Controller: images[]

    loop batch_size=1
        Controller->>Model: processor(images)
        Model-->>Controller: batch_features
        Controller->>Model: model.forward(**batch_features)
        Model-->>Controller: embeddings

        Controller->>Qdrant: upsert_with_retry(points)
        Controller->>Supabase: upload_images(images)
    end
```

### Response Model

```python
class IngestResponse(BaseModel):
    results: list[dict]  # [{filename, num_pages} or {filename, error}]
```

---

## endpoints/query.py - Query Endpoint

Handles document queries with streaming responses.

### QueryController

Controller class encapsulating query logic.

```mermaid
classDiagram
    class QueryController {
        -model: ColQwen2_5
        -processor: ColQwen2_5_Processor
        -qdrant_client: AsyncQdrantClient
        -collection_name: str
        -supabase_downloader: SupabaseJPEGDownloader
        -instructor_client: AsyncInstructor
        -prompts: dict

        +query(query, top_k, session_id) StreamingResponse
        -_embed_query(query) Tensor
        -_search_qdrant(embedding, session_id, top_k) List[ScoredPoint]
        -_build_prompt(images) str
    }
```

### Endpoint

#### `POST /query/`

```python
@router.post("/query/")
async def query(
    query: str = Form(...),
    top_k: int = Form(...),
    session_id: UUID4 = Form(...),
    model: ColQwen2_5 = Depends(get_colpali_model),
    processor: ColQwen2_5_Processor = Depends(get_colpali_processor),
    qdrant_client: AsyncQdrantClient = Depends(get_qdrant_client),
    collection_name: str = Depends(get_collection_name),
    supabase_downloader: SupabaseJPEGDownloader = Depends(get_supabase_downloader),
    instructor_client: AsyncInstructor = Depends(get_instructor_client),
    prompts: dict = Depends(get_prompts),
) -> StreamingResponse:
```

### Query Flow

```mermaid
sequenceDiagram
    participant Client
    participant Controller
    participant ColQwen as ColQwen2.5
    participant Qdrant
    participant Supabase
    participant Claude

    Client->>Controller: query, top_k, session_id

    Controller->>ColQwen: Embed query
    ColQwen-->>Controller: query_embedding

    Controller->>Qdrant: query_points(filter=session_id)
    Qdrant-->>Controller: scored_points[]

    Controller->>Supabase: download_instructor_images()
    Supabase-->>Controller: Image[]

    Controller->>Claude: create_partial(FinalResponse, stream=True)

    loop Streaming
        Claude-->>Controller: partial FinalResponse
        Controller-->>Client: SSE chunk
    end
```

### Streaming Implementation

```python
stream = self.instructor_client.completions.create_partial(
    model=self.llm_config["model"],
    response_model=FinalResponse,
    messages=[{"role": "user", "content": query_content}],
    context={"query": query},
    temperature=self.llm_config["temperature"],
    max_tokens=self.llm_config["max_tokens"],
    max_retries=3,
)

async for partial in stream:
    yield partial.model_dump_json() + "\n"

return StreamingResponse(
    controller.query(query, top_k, session_id),
    media_type="text/event-stream"
)
```

---

## Usage Example

```python
from fastapi import FastAPI, Depends
from src.app.api.lifespan import lifespan
from src.app.api.dependencies import get_qdrant_client

app = FastAPI(lifespan=lifespan)

@app.get("/example")
async def example(
    qdrant_client = Depends(get_qdrant_client)
):
    # Use qdrant_client...
    pass
```
