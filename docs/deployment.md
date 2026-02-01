# Deployment Guide

This document covers deployment options for the ColPali RAG App.

## Deployment Options Overview

```mermaid
graph TD
    subgraph Dev["Development"]
        Local["Local Development\n(make dev)"]
    end

    subgraph Container["Containerized"]
        Docker["Docker\n(make docker_run)"]
        Compose["Docker Compose\n(make docker_dev)"]
    end

    subgraph Cloud["Cloud Deployment"]
        GCP["Google Cloud Run"]
        AWS["AWS ECS/Fargate"]
        Azure["Azure Container Apps"]
    end

    subgraph GPU["GPU Cloud (Recommended)"]
        RunPod["RunPod\n(make docker_build_runpod)"]
    end

    Dev --> Container --> Cloud
    Container --> GPU
```

---

## Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.11+ | 3.12 |
| RAM | 8 GB | 16 GB |
| GPU | - | NVIDIA (CUDA 11.8+) |
| Disk | 10 GB | 20 GB |

### Software Dependencies

- [uv](https://github.com/astral-sh/uv) - Package manager
- [Poppler](https://poppler.freedesktop.org/) - PDF rendering (for pdf2image)
- Docker (for containerized deployment)

### External Services

- Qdrant Cloud or self-hosted instance
- Supabase project
- Anthropic API access

---

## Local Development

### Setup

```bash
# Clone repository
git clone https://github.com/your-org/colpali-rag-app.git
cd colpali-rag-app

# Install dependencies
uv sync --all-groups

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Initialize Qdrant collection
make create_collection
```

### Running the Server

```bash
# Start with hot-reload
make dev
```

The server will be available at `http://localhost:8000`.

### Development Workflow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant UV as uv
    participant Server as FastAPI
    participant Services as External Services

    Dev->>UV: uv sync --all-groups
    UV-->>Dev: Dependencies installed

    Dev->>Dev: Edit .env

    Dev->>Server: make create_collection
    Server->>Services: Create Qdrant collection

    Dev->>Server: make dev
    Note over Server: Hot-reload enabled
    Server-->>Dev: http://localhost:8000

    loop Development
        Dev->>Dev: Edit code
        Server->>Server: Auto-reload
    end
```

### Code Quality Commands

```bash
# Run all linters and formatters
make pretty

# Type checking
make mypy

# Run all checks
make all
```

---

## Docker Deployment

### Build Architecture

```mermaid
graph TD
    subgraph Multi-Stage["Multi-Stage Build"]
        Stage1["deps Stage\n(Install dependencies)"]
        Stage2["builder Stage\n(Add source code)"]
        Stage3["runtime Stage\n(Final image)"]
    end

    Stage1 --> Stage2 --> Stage3

    subgraph Output["Final Image"]
        Size["~2.1 GB"]
        Base["python:3.12-slim"]
    end

    Stage3 --> Output
```

### Building the Image

```bash
# Build production image
make docker_build

# Or manually
docker build -t colpali-rag-app:latest .
```

### Running the Container

```bash
# Run with .env file
make docker_run

# Or manually
docker run -p 8000:8000 --env-file .env colpali-rag-app:latest
```

### Docker Compose (Development)

```bash
# Start with hot-reload
make docker_dev
```

This mounts the source directory for live code updates.

### Docker Compose Configuration

```yaml
version: "3.8"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./src:/app/src  # Hot-reload support
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/docs"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Cloud Deployment

### Google Cloud Run

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GCR as Container Registry
    participant Run as Cloud Run
    participant Secrets as Secret Manager

    Dev->>GCR: docker push
    Dev->>Secrets: Store API keys
    Dev->>Run: gcloud run deploy
    Run->>GCR: Pull image
    Run->>Secrets: Inject secrets
    Run-->>Dev: Service URL
```

#### Deployment Steps

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build and push
docker build -t gcr.io/YOUR_PROJECT_ID/colpali-rag-app:latest .
docker push gcr.io/YOUR_PROJECT_ID/colpali-rag-app:latest

# Deploy
gcloud run deploy colpali-rag-app \
  --image gcr.io/YOUR_PROJECT_ID/colpali-rag-app:latest \
  --platform managed \
  --region us-central1 \
  --memory 4Gi \
  --cpu 2 \
  --set-secrets=QDRANT_API_KEY=qdrant-api-key:latest,\
                ANTHROPIC_API_KEY=anthropic-key:latest,\
                SUPABASE_KEY=supabase-key:latest \
  --set-env-vars=QDRANT_URL=your-qdrant-url,\
                 SUPABASE_URL=your-supabase-url,\
                 COLLECTION_NAME=your-collection
```

### AWS ECS/Fargate

#### Task Definition

```json
{
  "family": "colpali-rag-app",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "YOUR_ECR_REPO/colpali-rag-app:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "secrets": [
        {
          "name": "QDRANT_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:qdrant-key"
        },
        {
          "name": "ANTHROPIC_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:anthropic-key"
        },
        {
          "name": "SUPABASE_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:supabase-key"
        }
      ],
      "environment": [
        {"name": "QDRANT_URL", "value": "your-qdrant-url"},
        {"name": "SUPABASE_URL", "value": "your-supabase-url"},
        {"name": "COLLECTION_NAME", "value": "your-collection"}
      ]
    }
  ]
}
```

### Azure Container Apps

```bash
# Create container app
az containerapp create \
  --name colpali-rag-app \
  --resource-group YOUR_RG \
  --environment YOUR_ENV \
  --image YOUR_ACR.azurecr.io/colpali-rag-app:latest \
  --target-port 8000 \
  --ingress external \
  --cpu 2 --memory 4Gi \
  --secrets qdrant-key=YOUR_KEY anthropic-key=YOUR_KEY supabase-key=YOUR_KEY \
  --env-vars QDRANT_URL=your-url SUPABASE_URL=your-url COLLECTION_NAME=your-collection \
             QDRANT_API_KEY=secretref:qdrant-key \
             ANTHROPIC_API_KEY=secretref:anthropic-key \
             SUPABASE_KEY=secretref:supabase-key
```

### RunPod (GPU)

RunPod provides GPU instances ideal for running the ColQwen2.5 model with CUDA acceleration. The RunPod image includes **Flash Attention 2** pre-compiled for optimal inference performance.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GH as GitHub Actions
    participant DH as Docker Hub
    participant RP as RunPod

    Dev->>GH: Push to main
    GH->>GH: Build GPU image
    GH->>DH: Push image
    Dev->>RP: Deploy Pod
    RP->>DH: Pull image
    RP-->>Dev: Pod URL
```

#### Prerequisites

1. **Docker Hub Account** - Free tier works (public images)
2. **RunPod Account** - GPU cloud provider
3. **GitHub Repository** - For automated builds

#### Setup GitHub Secrets

Add these secrets to your GitHub repository (Settings → Secrets → Actions):

| Secret | Description |
|--------|-------------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token (create at hub.docker.com → Account Settings → Security) |

#### Automated Build (Recommended)

Push to `main` branch triggers GitHub Actions to build and push:

```bash
git push origin main
# Image built and pushed to: your-username/colpali-rag-app:latest
```

#### Manual Build

```bash
# Build GPU-optimized image (~12GB with model + Flash Attention 2)
make docker_build_runpod

# Push to Docker Hub
export DOCKERHUB_USERNAME=your-username
docker login
make docker_push_runpod
```

#### Deploy on RunPod

1. Go to **RunPod Console** → **Pods** → **Deploy**
2. Select GPU (minimum 16GB VRAM):
   - Budget: RTX 4000 Ada, A4000
   - Recommended: RTX 4090, A5000, A6000
3. Configure container:
   - **Image**: `your-dockerhub-username/colpali-rag-app:latest`
   - **Container Disk**: 20 GB
   - **HTTP Port**: 8000
4. Set environment variables:
   ```
   QDRANT_URL=https://your-qdrant-instance.cloud.qdrant.io
   QDRANT_API_KEY=your-qdrant-api-key
   COLLECTION_NAME=colpali
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-supabase-key
   ANTHROPIC_API_KEY=sk-ant-your-key
   ```
5. Deploy and access via the provided Pod URL

#### GPU Requirements

| GPU | VRAM | Status |
|-----|------|--------|
| RTX 3080 | 10GB | Minimum (may need optimization) |
| RTX 4000 Ada | 16GB | Works well |
| RTX 4090 | 24GB | Recommended |
| A4000 | 16GB | Works well |
| A5000/A6000 | 24-48GB | Optimal |

#### Cost Estimates

| Component | Cost |
|-----------|------|
| GitHub Actions | Free (2,000 min/month) |
| Docker Hub | Free (public repos) |
| RunPod (16GB GPU) | ~$0.20-0.40/hour |
| RunPod (24GB GPU) | ~$0.40-0.80/hour |

---

## Production Considerations

### Health Checks

The application includes a `/health` endpoint for load balancer probes:

```python
@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}
```

This endpoint is used by Docker health checks and container orchestrators (Kubernetes, RunPod, etc.).

### Scaling

```mermaid
graph TD
    subgraph Horizontal["Horizontal Scaling"]
        LB["Load Balancer"]
        I1["Instance 1"]
        I2["Instance 2"]
        I3["Instance N"]
    end

    subgraph Shared["Shared State"]
        Qdrant["Qdrant"]
        Supabase["Supabase"]
    end

    LB --> I1
    LB --> I2
    LB --> I3

    I1 --> Qdrant
    I2 --> Qdrant
    I3 --> Qdrant

    I1 --> Supabase
    I2 --> Supabase
    I3 --> Supabase
```

**Key Points:**
- Application is stateless (state stored in external services)
- Model loaded per instance (memory consideration)
- Consider GPU instances for faster inference

### Resource Recommendations

| Workload | CPU | Memory | GPU |
|----------|-----|--------|-----|
| Development | 2 cores | 4 GB | Optional |
| Production (light) | 2 cores | 8 GB | Optional |
| Production (heavy) | 4 cores | 16 GB | Recommended |

### Monitoring

```mermaid
graph LR
    subgraph App["Application"]
        Logs["Loguru Logs"]
        Metrics["Metrics"]
    end

    subgraph Observability["Observability Stack"]
        Loki["Loki / CloudWatch"]
        Prometheus["Prometheus"]
        Grafana["Grafana"]
    end

    Logs --> Loki
    Metrics --> Prometheus
    Loki --> Grafana
    Prometheus --> Grafana
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Out of memory | Model too large | Increase memory or use CPU |
| PDF conversion fails | Missing Poppler | Install Poppler |
| Connection refused (Qdrant) | Wrong URL or firewall | Check URL and network |
| Authentication error | Invalid API key | Verify API keys |
| Slow inference | No GPU | Use CUDA-enabled instance |

### Debug Mode

Enable debug logging:

```python
# In logging_config.py
logger.add(sys.stderr, level="DEBUG")
```

### Container Debugging

```bash
# Shell into running container
docker exec -it <container_id> /bin/bash

# Check logs
docker logs <container_id>

# Inspect environment
docker exec <container_id> env | grep -E "(QDRANT|SUPABASE|ANTHROPIC)"
```
