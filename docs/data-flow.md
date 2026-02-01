# Data Flow

This document describes the complete data flow through the ColPali RAG App system.

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

    subgraph Storage["Storage Layer"]
        Qdrant["Qdrant Vectors"]
        Supabase["Supabase Images"]
    end

    PDF --> Images --> Embeddings --> Qdrant
    Images --> Supabase

    UserQuery --> QueryEmbed --> Qdrant
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
    participant Controller as PDFIngestController
    participant PDF2Image as pdf2image
    participant ColQwen as ColQwen 2.5
    participant Qdrant
    participant Supabase

    Client->>Controller: POST /ingest-pdfs/
    Note over Controller: files, session_id

    rect rgb(240, 248, 255)
        Note over Controller,PDF2Image: PDF Conversion
        Controller->>PDF2Image: convert_from_bytes()
        Note over PDF2Image: 300 DPI, 4 threads
        PDF2Image-->>Controller: List[PIL.Image]
    end

    rect rgb(255, 248, 240)
        Note over Controller,ColQwen: Embedding Generation
        loop For each batch
            Controller->>ColQwen: Process images
            Note over ColQwen: torch.inference_mode()
            ColQwen-->>Controller: embeddings (128-dim)
        end
    end

    rect rgb(240, 255, 240)
        Note over Controller,Qdrant: Vector Storage
        Controller->>Qdrant: upsert_with_retry()
        Note over Qdrant: Multi-vector points
        Qdrant-->>Controller: Confirmation
    end

    rect rgb(255, 240, 255)
        Note over Controller,Supabase: Image Storage
        Controller->>Supabase: upload_images()
        Note over Supabase: {session}/{doc}/{page}.jpeg
        Supabase-->>Controller: Confirmation
    end

    Controller-->>Client: IngestResponse
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

    subgraph Step2["Step 2: Processing"]
        C["Processed Batch\n(BatchFeature)"]
    end

    subgraph Step3["Step 3: Embedding"]
        D["Embeddings\n(Tensor[N, 128])"]
    end

    subgraph Step4["Step 4: Points"]
        E["Qdrant Points\n(PointStruct)"]
    end

    A -->|"pdf2image\n300 DPI"| B
    B -->|"processor()"| C
    C -->|"model.forward()"| D
    D -->|"to_list()"| E
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
            VN["...128 dimensions..."]
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
    participant Controller as QueryController
    participant ColQwen as ColQwen 2.5
    participant Qdrant
    participant Supabase
    participant Claude as Claude Sonnet 3.7

    Client->>Controller: POST /query/
    Note over Controller: query, top_k, session_id

    rect rgb(240, 248, 255)
        Note over Controller,ColQwen: Query Embedding
        Controller->>ColQwen: Process query text
        ColQwen-->>Controller: query_embedding
    end

    rect rgb(255, 248, 240)
        Note over Controller,Qdrant: Vector Search
        Controller->>Qdrant: query_points()
        Note over Qdrant: filter: session_id
        Qdrant-->>Controller: ScoredPoints[]
    end

    rect rgb(240, 255, 240)
        Note over Controller,Supabase: Image Retrieval
        Controller->>Supabase: download_instructor_images()
        Supabase-->>Controller: Image[] (base64)
    end

    rect rgb(255, 240, 255)
        Note over Controller,Claude: Response Generation
        Controller->>Claude: create_partial()
        Note over Claude: stream=True
        loop Streaming
            Claude-->>Controller: Partial FinalResponse
            Controller-->>Client: SSE chunk
        end
    end
```

### Search Parameters

```mermaid
graph LR
    subgraph Query["Query Request"]
        Q["query: string"]
        K["top_k: int"]
        S["session_id: UUID"]
    end

    subgraph Qdrant["Qdrant Query"]
        Embed["Query Embedding"]
        Filter["Filter Condition"]
        Limit["Limit: top_k"]
    end

    Q -->|"ColQwen"| Embed
    S --> Filter
    K --> Limit
```

### Prompt Construction

```mermaid
graph TD
    subgraph Prompts["Prompt Files"]
        P1["prompts/response_1\n(System Instructions)"]
        P2["prompts/response_2\n(Output Format)"]
    end

    subgraph Images["Retrieved Images"]
        I1["Image 1"]
        I2["Image 2"]
        I3["Image N"]
    end

    subgraph Message["Final Message"]
        M1["prompt_1 text"]
        M2["<image>Image 1</image>"]
        M3["<image>Image 2</image>"]
        M4["<image>Image N</image>"]
        M5["prompt_2 text"]
    end

    P1 --> M1
    I1 --> M2
    I2 --> M3
    I3 --> M4
    P2 --> M5
```

### Streaming Response

```mermaid
sequenceDiagram
    participant Claude as Claude API
    participant Instructor
    participant Controller
    participant Client

    Controller->>Instructor: create_partial(stream=True)
    Instructor->>Claude: API Request

    loop For each chunk
        Claude-->>Instructor: Partial JSON
        Instructor-->>Controller: FinalResponse (partial)
        Controller->>Controller: model_dump_json()
        Controller-->>Client: SSE: data + newline
    end

    Note over Client: Final response assembled
```

---

## Data Models

### Ingestion Data Flow

```mermaid
classDiagram
    class UploadFile {
        +filename: str
        +file: SpooledTemporaryFile
        +content_type: str
        +read() bytes
    }

    class PILImage {
        +mode: str
        +size: tuple
        +save(fp, format)
    }

    class BatchFeature {
        +input_ids: Tensor
        +attention_mask: Tensor
        +pixel_values: Tensor
    }

    class Embeddings {
        +shape: [batch, 128]
        +dtype: float32
    }

    class PointStruct {
        +id: str
        +vector: dict
        +payload: dict
    }

    UploadFile --> PILImage : pdf2image
    PILImage --> BatchFeature : processor
    BatchFeature --> Embeddings : model
    Embeddings --> PointStruct : to_list
```

### Query Data Flow

```mermaid
classDiagram
    class QueryRequest {
        +query: str
        +top_k: int
        +session_id: UUID4
    }

    class ScoredPoint {
        +id: str
        +score: float
        +payload: dict
    }

    class InstructorImage {
        +source: dict
        +type: str
    }

    class Reference {
        +id: int
        +title: str
        +filename: str
    }

    class FinalResponse {
        +references: list[Reference]
        +answer: str
    }

    QueryRequest --> ScoredPoint : qdrant search
    ScoredPoint --> InstructorImage : supabase download
    InstructorImage --> FinalResponse : claude generate
    FinalResponse --> Reference : contains
```

---

## Concurrency Model

### Parallel Operations

```mermaid
graph TB
    subgraph Ingestion["Ingestion (per document)"]
        direction LR
        Convert["PDF → Images\n(4 threads)"]
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
    participant Controller
    participant Batch1
    participant Batch2
    participant BatchN

    Note over Controller: batch_size = 1

    Controller->>Batch1: Process images[0:1]
    Batch1-->>Controller: embeddings
    Controller->>Controller: Upsert + Upload

    Controller->>Batch2: Process images[1:2]
    Batch2-->>Controller: embeddings
    Controller->>Controller: Upsert + Upload

    Controller->>BatchN: Process images[n-1:n]
    BatchN-->>Controller: embeddings
    Controller->>Controller: Upsert + Upload
```

---

## Error Handling Flow

```mermaid
graph TD
    subgraph Operation["Operation"]
        O["Qdrant Upsert"]
    end

    subgraph Retry["Retry Logic (Tenacity)"]
        R1["Attempt 1"]
        R2["Attempt 2 (1s backoff)"]
        R3["Attempt 3 (2s backoff)"]
        Fail["Raise Exception"]
    end

    O --> R1
    R1 -->|"Exception"| R2
    R2 -->|"Exception"| R3
    R3 -->|"Exception"| Fail
    R1 -->|"Success"| Success["Continue"]
    R2 -->|"Success"| Success
    R3 -->|"Success"| Success
```
