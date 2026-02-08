.PHONY: clean-pycache clean-ruff-cache clean-mypy-cache clean-all \
        lint format imports mypy pretty all \
		dev dev_vlm dev_api \
		docker_up docker_up_detach docker_logs docker_down \
		docker_runpod_up docker_runpod_up_detach docker_runpod_logs docker_runpod_down \
		docker_build_vlm docker_build_vlm_runpod docker_push_vlm docker_push_vlm_runpod \
		docker_build_api docker_push_api

include .env

# ==============================================================================
# Root-Level Commands (for both services)
# ==============================================================================

# ------------------------------------------------------------------------------
# Cleaning Targets
# ------------------------------------------------------------------------------
clean-pycache:
	find ./ -type d -name '__pycache__' -exec rm -rf {} +

clean-ruff-cache:
	find ./ -type d -name '.ruff_cache' -exec rm -rf {} +

clean-mypy-cache:
	find ./ -type d -name '.mypy_cache' -exec rm -rf {} +

clean-all: clean-pycache clean-ruff-cache clean-mypy-cache

# ------------------------------------------------------------------------------
# Code Quality (runs on both services)
# ------------------------------------------------------------------------------
lint:
	cd colpali-vlm && uv run ruff check src/* --fix && uv run ruff check server.py --fix
	cd document-api && uv run ruff check src/* --fix && uv run ruff check server.py --fix

format:
	cd colpali-vlm && uv run ruff format src/* && uv run ruff format server.py
	cd document-api && uv run ruff format src/* && uv run ruff format server.py

imports:
	cd colpali-vlm && uv run ruff check src/* --select I --fix && uv run ruff check server.py --select I --fix
	cd document-api && uv run ruff check src/* --select I --fix && uv run ruff check server.py --select I --fix

mypy:
	cd colpali-vlm && uv run mypy src server.py
	cd document-api && uv run mypy src server.py

pretty: lint format imports

all: pretty mypy clean-all

# ------------------------------------------------------------------------------
# Development (local, without Docker)
# ------------------------------------------------------------------------------
# Test dependencies locally before Docker rebuild
test_deps_vlm:
	cd colpali-vlm && uv sync && uv run python -c "import auto_round, auto_gptq, bitsandbytes; print('✅ All quantization libraries installed')"

test_deps_api:
	cd document-api && uv sync && uv run python -c "import anthropic, qdrant_client; print('✅ All API dependencies installed')"

test_deps: test_deps_vlm test_deps_api

# Start VLM service (port 8001)
dev_vlm:
	cd colpali-vlm && uv run uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Start API service (port 8000) - requires VLM service running
dev_api:
	cd document-api && VLM_SERVICE_URL=http://localhost:8001 uv run uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Start both services (run in separate terminals)
dev:
	@echo "Run 'make dev_vlm' in one terminal and 'make dev_api' in another"

# ------------------------------------------------------------------------------
# Docker Compose (Development - both services)
# ------------------------------------------------------------------------------
docker_up:
	docker compose up --build

docker_up_detach:
	docker compose up -d --build

docker_logs:
	docker compose logs -f --tail=100

docker_down:
	docker compose down

# ------------------------------------------------------------------------------
# Docker Compose (RunPod - VLM with baked-in models)
# ------------------------------------------------------------------------------
docker_runpod_up:
	docker compose -f docker-compose.runpod.yml up --build

docker_runpod_up_detach:
	docker compose -f docker-compose.runpod.yml up -d --build

docker_runpod_logs:
	docker compose -f docker-compose.runpod.yml logs -f --tail=100

docker_runpod_down:
	docker compose -f docker-compose.runpod.yml down

# ------------------------------------------------------------------------------
# Docker Build & Push (VLM Service - for RunPod)
# ------------------------------------------------------------------------------
# Build local development image (runtime model download, works with all models)
docker_build_vlm:
	cd colpali-vlm && docker build -f Dockerfile.local -t colpali-vlm:latest .

# Build RunPod image (baked-in models, ~15-20GB for single model)
# Usage: make docker_build_vlm_runpod COLPALI_MODEL=TomoroAI/tomoro-colqwen3-embed-4b
# Or: make docker_build_vlm_runpod COLPALI_MODEL=vidore/colqwen2.5-v0.2
docker_build_vlm_runpod:
	cd colpali-vlm && docker build -f Dockerfile.runpod --build-arg COLPALI_MODEL=$(or $(COLPALI_MODEL),TomoroAI/tomoro-colqwen3-embed-4b) -t colpali-vlm:runpod .

# Build with TomoroAI model (default, 320-dim)
docker_build_vlm_runpod_tomoroai:
	cd colpali-vlm && docker build -f Dockerfile.runpod --build-arg COLPALI_MODEL=TomoroAI/tomoro-colqwen3-embed-4b -t colpali-vlm:runpod .

# Build with ColQwen2.5 model (128-dim, smaller)
docker_build_vlm_runpod_colqwen2_5:
	cd colpali-vlm && docker build -f Dockerfile.runpod --build-arg COLPALI_MODEL=vidore/colqwen2.5-v0.2 -t colpali-vlm:runpod .

# Push local development image to Docker Hub
docker_push_vlm:
	docker tag colpali-vlm:latest $(DOCKERHUB_USERNAME)/colpali-vlm:latest
	docker push $(DOCKERHUB_USERNAME)/colpali-vlm:latest

# Push RunPod image to Docker Hub
docker_push_vlm_runpod:
	docker tag colpali-vlm:runpod $(DOCKERHUB_USERNAME)/colpali-vlm:runpod
	docker push $(DOCKERHUB_USERNAME)/colpali-vlm:runpod

# ------------------------------------------------------------------------------
# Docker Build & Push (Document API)
# ------------------------------------------------------------------------------
# Build Document API image	
docker_build_api:
	cd document-api && docker build -t document-api:latest .

# Push Document API image to Docker Hub
docker_push_api:
	docker tag document-api:latest $(DOCKERHUB_USERNAME)/document-api:latest
	docker push $(DOCKERHUB_USERNAME)/document-api:latest

# ------------------------------------------------------------------------------
# Combined Build & Push
# ------------------------------------------------------------------------------
# Build all images
docker_build_all: docker_build_vlm docker_build_api

# Push all images to Docker Hub
docker_push_all: docker_push_vlm docker_push_api

# Build DBC image
docker_build_dbc:
	cd colpali-vlm && docker buildx build --progress=plain -f Dockerfile.dbc --build-arg COLPALI_MODEL=$(or $(COLPALI_MODEL),TomoroAI/tomoro-colqwen3-embed-4b) -t $(DOCKERHUB_USERNAME)/colpali-vlm:dbc --push .

# Push DBC image to Docker Hub
docker_push_dbc:
	docker tag colpali-vlm:dbc $(DOCKERHUB_USERNAME)/colpali-vlm:dbc
	docker push $(DOCKERHUB_USERNAME)/colpali-vlm:dbc
