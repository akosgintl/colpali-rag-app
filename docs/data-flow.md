# Data Flow

This document describes the complete data flow through the ColPali RAG App's three-service architecture.

## Overview

```mermaid
graph TB
    subgraph Ingestion["Ingestion Pipeline"]
        PDF["PDF Documents"]
        Images["JPEG Images"]
        Embeddings["Vector Embeddings"]
    end

    subgraph Query["Query Pipeline"]
        UserQuery["User Query"]
        QueryEmbed["Query Embedding"]
        Results["Search Results"]
        Response["Generated Response"]
    end

    subgraph Services["Services"]
        API["Document API (:8000)"]
        VLM["VLM Service (:8001)"]
    end

    subgraph Storage["Storage Layer"]
        Qdrant["Qdrant Vectors"]
        Supabase["Supabase Images"]
    end

    PDF --> API
    API --> Images
    Images -->|HTTP| VLM
    VLM --> Embeddings
    Embeddings --> Qdrant
    Images --> Supabase

    UserQuery --> API
    API -->|HTTP| VLM
    VLM --> QueryEmbed
    QueryEmbed --> Qdrant
    Qdrant --> Results
    Supabase --> Results
    Results --> Response
```

---

## Ingestion Pipeline

The ingestion pipeline processes PDF documents and prepares them for retrieval.

### Step-by-Step Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as Document API
    participant PDF2Image as pdf2image
    participant VLM as VLM Service
    participant Qdrant
    participant Supabase

    Client->>API: POST /ingest-pdfs/
    Note over API: files, session_id

    rect rgb(240, 248, 255)
        Note over API,PDF2Image: PDF Conversion
        API->>PDF2Image: convert_from_bytes()
        Note over PDF2Image: 300 DPI, 4 threads
        PDF2Image-->>API: List[PIL.Image]
    end

    rect rgb(255, 248, 240)
        Note over API,VLM: Embedding Generation (HTTP)
        loop For each batch (default: 5 pages)
            API->>VLM: POST /embed/images
            Note over VLM: torch.inference_mode()
            VLM-->>API: embeddings (128/320-dim)
        end
    end

    rect rgb(240, 255, 240)
        Note over API,Qdrant: Vector Storage
        API->>Qdrant: upsert_with_retry()
        Note over Qdrant: Multi-vector points
        Qdrant-->>API: Confirmation
    end

    rect rgb(255, 240, 255)
        Note over API,Supabase: Image Storage
        API->>Supabase: upload_images()
        Note over Supabase: {session}/{doc}/{page}.jpeg
        Supabase-->>API: Confirmation
    end

    API-->>Client: IngestResponse
```

### Data Transformations

```mermaid
graph LR
    subgraph Input
        A["PDF File\n(bytes)"]
    end

    subgraph Step1["Step 1: Conversion"]
        B["JPEG Images\n(PIL.Image)"]
    end

    subgraph Step2["Step 2: HTTP to VLM"]
        C["Multipart Upload\n(JPEG files)"]
    end

    subgraph Step3["Step 3: Embedding"]
        D["Embeddings\n(list[list[float]])"]
    end

    subgraph Step4["Step 4: Points"]
        E["Qdrant Points\n(PointStruct)"]
    end

    A -->|"pdf2image\n300 DPI"| B
    B -->|"VLMClient\nPOST /embed/images"| C
    C -->|"VLM model\ninference"| D
    D -->|"to PointStruct"| E
```

### Qdrant Point Structure

Each page becomes a multi-vector point in Qdrant:

```mermaid
graph TD
    subgraph Point["Qdrant Point"]
        ID["id: UUID"]
        subgraph Vector["vector (multi-vector)"]
            V1["[0.1, 0.2, ..., 0.8]"]
            V2["[0.3, 0.1, ..., 0.5]"]
            VN["...128 or 320 dimensions..."]
        end
        subgraph Payload["payload"]
            SID["session_id: UUID"]
            DOC["document: string"]
            PAGE["page: int"]
        end
    end
```

### Supabase Storage Structure

```mermaid
graph TD
    subgraph Bucket["colpali bucket"]
        subgraph Session["/{session_id}/"]
            subgraph Doc1["/{document1}/"]
                P1["1.jpeg"]
                P2["2.jpeg"]
                P3["3.jpeg"]
            end
            subgraph Doc2["/{document2}/"]
                P4["1.jpeg"]
                P5["2.jpeg"]
            end
        end
    end
```

---

## Query Pipeline

The query pipeline retrieves relevant documents and generates responses.

### Step-by-Step Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as Document API
    participant VLM as VLM Service
    participant Qdrant
    participant Supabase
    participant MLM as Multimodal LM (Qwen3-VL)

    Client->>API: POST /query/
    Note over API: query, top_k, session_id

    rect rgb(240, 248, 255)
        Note over API,VLM: Query Embedding (HTTP)
        API->>VLM: POST /embed/query
        VLM-->>API: query_embedding
    end

    rect rgb(255, 248, 240)
        Note over API,Qdrant: Vector Search
        API->>Qdrant: query_points()
        Note over Qdrant: filter: session_id
        Qdrant-->>API: ScoredPoints[]
    end

    rect rgb(240, 255, 240)
        Note over API,Supabase: Image Retrieval
        API->>Supabase: download_base64_images()
        Supabase-->>API: list[str] (base64)
    end

    rect rgb(255, 240, 255)
        Note over API,MLM: Response Generation
        API->>MLM: POST /v1/chat/completions
        Note over MLM: stream=True, vision messages
        loop Streaming
            MLM-->>API: delta.content
            API-->>Client: SSE chunk (data: text)
        end
    end
```

---

## Error Handling Flow

### VLM Client Errors

```mermaid
graph TD
    subgraph VLMClient["VLMClient (httpx + tenacity)"]
        Request["embed_images() / embed_query()"]
        Retry1["Attempt 1"]
        Retry2["Attempt 2 (1s backoff)"]
        Retry3["Attempt 3 (2s backoff)"]
    end

    subgraph Errors["Error Types"]
        ConnErr["VLMServiceUnavailable\n(connection failed)"]
        InfErr["VLMInferenceError\n(504 timeout or HTTP error)"]
        GenErr["VLMClientError\n(base exception)"]
    end

    Request --> Retry1
    Retry1 -->|"httpx error"| Retry2
    Retry2 -->|"httpx error"| Retry3
    Retry3 -->|"ConnectError"| ConnErr
    Retry3 -->|"504"| InfErr
    Retry3 -->|"Other HTTP"| GenErr
    Retry1 -->|"Success"| Success["Return embeddings"]
```

### Qdrant Retry

```mermaid
graph TD
    Start["upsert_with_retry()"]
    Attempt1["Attempt 1"]
    Attempt2["Attempt 2 (1s backoff)"]
    Attempt3["Attempt 3 (2s backoff)"]
    Success["Return None"]
    Failure["Raise Exception"]

    Start --> Attempt1
    Attempt1 -->|Success| Success
    Attempt1 -->|Exception| Attempt2
    Attempt2 -->|Success| Success
    Attempt2 -->|Exception| Attempt3
    Attempt3 -->|Success| Success
    Attempt3 -->|Exception| Failure
```

---

## Concurrency Model

### Semaphores

| Service | Semaphore | Limit | Purpose |
|---------|-----------|-------|---------|
| VLM Service | `model_semaphore` | 1 (configurable) | Prevents concurrent GPU access |
| Document API | `qdrant_semaphore` | 10 | Prevents Qdrant connection pool exhaustion |

### Parallel Operations

```mermaid
graph TB
    subgraph Ingestion["Ingestion (per document)"]
        direction LR
        Convert["PDF to Images\n(4 threads)"]
        Upload["Image Upload\n(asyncio.gather)"]
    end

    subgraph Query["Query"]
        direction LR
        Download["Image Download\n(asyncio.gather)"]
    end
```

### Batch Processing

```mermaid
sequenceDiagram
    participant API as Document API
    participant VLM as VLM Service
    participant Qdrant
    participant Supabase

    Note over API: batch_size = 5 (default)

    API->>VLM: POST /embed/images (pages 1-5)
    VLM-->>API: embeddings
    API->>Qdrant: upsert_with_retry(points)
    API->>Supabase: upload_images(batch)

    API->>VLM: POST /embed/images (pages 6-10)
    VLM-->>API: embeddings
    API->>Qdrant: upsert_with_retry(points)
    API->>Supabase: upload_images(batch)
```
