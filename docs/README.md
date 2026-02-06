# ColPali RAG App Documentation

Welcome to the ColPali RAG App documentation. This application provides a two-microservice backend for document retrieval using Vision Language Models (VLMs).

## What is ColPali RAG App?

ColPali RAG App uses **ColQwen 2.5**, **ColQwen3**, or **TomoroAI ColQwen3** to index and retrieve information directly from document images, preserving visual elements like tables, figures, and charts. Unlike traditional text-based RAG systems, this approach maintains the full visual context of documents.

The system is split into two independently deployable services:
- **colpali-vlm/** - GPU-based VLM embedding service
- **document-api/** - CPU-based API orchestration service

## Quick Links

| Document | Description |
|----------|-------------|
| [Architecture Overview](./architecture.md) | Two-service design and component relationships |
| [API Reference](./api-reference.md) | VLM and Document API endpoint documentation |
| [Data Flow](./data-flow.md) | Request lifecycle and inter-service communication |
| [Configuration](./configuration.md) | Environment variables and settings for both services |
| [Deployment](./deployment.md) | Local, Docker, RunPod (GPU), and cloud deployment |

## Module Documentation

| Module | Description |
|--------|-------------|
| [API Module](./modules/api.md) | FastAPI endpoints, dependencies, and lifespan for both services |
| [ColPali Module](./modules/colpali.md) | Multi-model loader factory (ColQwen2.5, ColQwen3, TomoroAI) |
| [Services Module](./modules/services.md) | VLM client, image upload/download services |
| [Models Module](./modules/models.md) | Pydantic data models |
| [Utils Module](./modules/utils.md) | Utility functions |
| [Settings Module](./modules/settings.md) | Configuration management for both services |

## Technology Stack

```mermaid
block-beta
    columns 4

    block:client:1
        A["Client Application"]
    end

    block:api:1
        B["Document API\n(CPU, :8000)"]
    end

    block:vlm:1
        C["VLM Service\n(GPU, :8001)"]
    end

    block:models:1
        D["ColQwen2.5\nColQwen3\nTomoroAI"]
    end

    block:storage:4
        E["Qdrant\n(Vectors)"]
        F["Supabase\n(Images)"]
        G["Claude Sonnet 4\n(LLM)"]
    end

    A --> B
    B --> C
    C --> D
    B --> E
    B --> F
    B --> G
```

## Core Technologies

| Technology | Service | Purpose |
|------------|---------|---------|
| **FastAPI** | Both | Async web framework |
| **ColQwen 2.5 / ColQwen3 / TomoroAI** | VLM | Vision-language models for embeddings |
| **httpx + tenacity** | Document API | HTTP client for VLM service with retry |
| **Qdrant** | Document API | Vector database for similarity search |
| **Supabase** | Document API | Cloud storage for document images |
| **Claude Sonnet 4** | Document API | LLM for response generation |
| **Instructor** | Document API | Structured output validation |

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Poppler (for PDF conversion, Document API only)
- NVIDIA GPU (for VLM service)
- Access to Qdrant, Supabase, and Anthropic APIs

### Quick Start

```bash
# Configure environment for both services
cp colpali-vlm/.env.example colpali-vlm/.env
cp document-api/.env.example document-api/.env
# Edit both .env files with your credentials

# Option 1: Docker Compose (both services)
make docker_up

# Option 2: Local development (two terminals)
# Terminal 1: VLM service (requires GPU)
make dev_vlm

# Terminal 2: Document API
make dev_api
```

- Document API: `http://localhost:8000`
- VLM Service: `http://localhost:8001`

## License

See the root [LICENSE](../LICENSE) file for details.
