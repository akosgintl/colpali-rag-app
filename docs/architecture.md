# Architecture Overview

This document describes the system architecture of the ColPali RAG App.

## High-Level Architecture

```mermaid
graph TB
    subgraph Client["Client Layer"]
        CLI["CLI / SDK"]
        Web["Web Application"]
    end

    subgraph API["FastAPI Application"]
        Router["Router Layer"]
        Deps["Dependency Injection"]
        Lifespan["Lifespan Manager"]
    end

    subgraph ML["ML Layer"]
        ColQwen["ColQwen 2.5 Model"]
        Processor["ColQwen Processor"]
    end

    subgraph External["External Services"]
        Qdrant["Qdrant Vector DB"]
        Supabase["Supabase Storage"]
        Anthropic["Claude Sonnet 3.7"]
    end

    CLI --> Router
    Web --> Router
    Router --> Deps
    Deps --> Lifespan
    Lifespan --> ColQwen
    Lifespan --> Processor
    Lifespan --> Qdrant
    Lifespan --> Supabase
    Lifespan --> Anthropic
```

## Component Architecture

```mermaid
graph TD
    subgraph Endpoints["Endpoints"]
        ingest["/ingest-pdfs/"]
        query["/query/"]
    end

    subgraph Dependencies["Dependencies"]
        dep1["get_qdrant_client"]
        dep2["get_colpali_model"]
        dep3["get_instructor_client"]
    end

    subgraph Services["Services"]
        uploader["SupabaseJPEGUploader"]
        downloader["SupabaseJPEGDownloader"]
    end

    subgraph Utilities["Utilities"]
        prompt["prompt_utils"]
        qdrant_u["qdrant_utils"]
    end

    ingest --> dep1
    ingest --> dep2
    ingest --> uploader
    query --> dep1
    query --> dep2
    query --> dep3
    query --> downloader
    uploader --> qdrant_u
    downloader --> prompt
```

## Directory Structure

```
colpali-rag-app/
├── server.py                 # Application entry point
├── scripts/
│   └── create_collection.py  # Qdrant initialization
├── prompts/
│   ├── response_1            # System prompt part 1
│   └── response_2            # System prompt part 2
└── src/app/
    ├── settings.py           # Configuration
    ├── logging_config.py     # Logging setup
    ├── api/
    │   ├── state.py          # Client factories
    │   ├── lifespan.py       # Lifecycle management
    │   ├── dependencies.py   # DI functions
    │   └── endpoints/
    │       ├── pdf_ingest.py # Ingestion endpoint
    │       └── query.py      # Query endpoint
    ├── colpali/
    │   └── loaders.py        # Model loading
    ├── models/
    │   └── query_response.py # Response models
    ├── services/
    │   ├── img_uploader.py   # Upload service
    │   └── img_downloader.py # Download service
    └── utils/
        ├── prompt_utils.py   # Prompt loading
        └── qdrant_utils.py   # Qdrant helpers
```

## Application Lifecycle

```mermaid
sequenceDiagram
    participant App as FastAPI App
    participant Life as Lifespan Manager
    participant State as State Factory
    participant ML as ColQwen2.5
    participant Ext as External Services

    Note over App: Application Startup
    App->>Life: Enter lifespan context
    Life->>State: Create Qdrant client
    State-->>Life: AsyncQdrantClient
    Life->>State: Create Supabase client
    State-->>Life: AsyncClient
    Life->>State: Create Anthropic client
    State-->>Life: AsyncAnthropic
    Life->>ML: Load model & processor
    ML-->>Life: ColQwen2.5, Processor
    Life-->>App: Yield State dict

    Note over App: Application Running
    App->>App: Handle requests

    Note over App: Application Shutdown
    App->>Life: Exit lifespan context
    Life->>Ext: Close Qdrant client
    Life->>Ext: Close Anthropic client
    Life-->>App: Cleanup complete
```

## State Management

The application uses FastAPI's lifespan pattern for state management:

```mermaid
graph LR
    subgraph Lifespan["Lifespan Context Manager"]
        Init["Initialize Clients"]
        State["State TypedDict"]
        Cleanup["Cleanup Resources"]
    end

    subgraph Request["Request Handling"]
        Deps["Dependencies"]
        Endpoint["Endpoint Handler"]
    end

    Init --> State
    State --> Deps
    Deps --> Endpoint
    State --> Cleanup
```

### State TypedDict Fields

| Field | Type | Description |
|-------|------|-------------|
| `model` | `ColQwen2_5` | Loaded vision-language model |
| `processor` | `ColQwen2_5_Processor` | Image/text processor |
| `supabase_uploader` | `SupabaseJPEGUploader` | Image upload service |
| `supabase_downloader` | `SupabaseJPEGDownloader` | Image download service |
| `instructor_client` | `AsyncInstructor` | Structured LLM client |
| `qdrant_client` | `AsyncQdrantClient` | Vector DB client |
| `collection_name` | `str` | Qdrant collection name |

## Dependency Injection

```mermaid
graph TD
    subgraph Request["Incoming Request"]
        R["Request Object"]
    end

    subgraph State["Application State"]
        S["request.state"]
    end

    subgraph Dependencies["Dependency Functions"]
        D1["get_qdrant_client()"]
        D2["get_colpali_model()"]
        D3["get_colpali_processor()"]
        D4["get_supabase_uploader()"]
        D5["get_supabase_downloader()"]
        D6["get_collection_name()"]
        D7["get_instructor_client()"]
        D8["get_prompts()"]
    end

    subgraph Endpoint["Endpoint Handler"]
        E["Handler Function"]
    end

    R --> S
    S --> D1
    S --> D2
    S --> D3
    S --> D4
    S --> D5
    S --> D6
    S --> D7
    D8 --> E
    D1 --> E
    D2 --> E
    D3 --> E
    D4 --> E
    D5 --> E
    D6 --> E
    D7 --> E
```

## External Service Integration

### Qdrant (Vector Database)

```mermaid
graph LR
    subgraph App["Application"]
        Embed["Embeddings"]
        Query["Query Vector"]
    end

    subgraph Qdrant["Qdrant"]
        Collection["Collection"]
        Index["Session ID Index"]
        Vectors["Multi-Vectors"]
    end

    Embed -->|Upsert| Collection
    Query -->|Search| Collection
    Collection --> Index
    Collection --> Vectors
```

**Collection Configuration:**
- Vector size: 128
- Distance: Cosine with MaxSim
- Multi-vector support enabled
- Indexed field: `session_id`

### Supabase (Object Storage)

```mermaid
graph LR
    subgraph App["Application"]
        Upload["Upload Service"]
        Download["Download Service"]
    end

    subgraph Supabase["Supabase Storage"]
        Bucket["colpali bucket"]
        subgraph Structure["Path Structure"]
            Session["/{session_id}/"]
            Doc["/{document}/"]
            Page["/{page}.jpeg"]
        end
    end

    Upload -->|JPEG| Bucket
    Download -->|JPEG| Bucket
    Bucket --> Session --> Doc --> Page
```

### Anthropic (LLM)

```mermaid
graph LR
    subgraph App["Application"]
        Instructor["Instructor Client"]
        Images["Document Images"]
        Prompts["System Prompts"]
    end

    subgraph Anthropic["Claude Sonnet 3.7"]
        Vision["Vision Processing"]
        Generate["Text Generation"]
    end

    subgraph Response["Structured Response"]
        Refs["References"]
        Answer["Answer"]
    end

    Instructor --> Vision
    Images --> Vision
    Prompts --> Vision
    Vision --> Generate
    Generate --> Refs
    Generate --> Answer
```

## Design Patterns

### 1. Factory Pattern
Client creation is delegated to factory functions in `state.py`.

### 2. Dependency Injection
FastAPI's `Depends()` provides loose coupling between endpoints and services.

### 3. Context Manager Pattern
Lifespan context manager ensures proper resource initialization and cleanup.

### 4. Repository Pattern
Services abstract storage operations (Supabase uploader/downloader).

### 5. Streaming Pattern
Query responses use Server-Sent Events for real-time output.

### 6. Retry Pattern
Qdrant operations use Tenacity for automatic retry with exponential backoff.
