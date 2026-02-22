.PHONY: clean-pycache clean-ruff-cache clean-mypy-cache clean-all \
        lint format imports mypy pretty all \
		dev dev_vlm dev_api test_deps_vlm test_deps_api test_deps \
		docker_up docker_up_detach docker_logs docker_down \
		docker_runpod_up docker_runpod_up_detach docker_runpod_logs docker_runpod_down \
		docker_build_vlm docker_push_vlm \
		docker_build_mlm docker_push_mlm \
		docker_build_api docker_push_api \
		docker_build_all docker_push_all

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
	cd colpali-vlm && uv sync && uv run python -c "import auto_round, auto_gptq, bitsandbytes; print('All quantization libraries installed')"

test_deps_api:
	cd document-api && uv sync && uv run python -c "import openai, qdrant_client; print('All API dependencies installed')"

test_deps: test_deps_vlm test_deps_api

# Start VLM service (port 8001)
dev_vlm:
	cd colpali-vlm && uv run uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Start API service (port 8000) - requires VLM and multimodal LM services running
dev_api:
	cd document-api && VLM_SERVICE_URL=http://localhost:8001 MULTIMODAL_LM_SERVICE_URL=http://localhost:8002 uv run uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Start all services (run in separate terminals)
dev:
	@echo "Run 'make dev_vlm' in one terminal and 'make dev_api' in another"
	@echo "Multimodal LM requires GPU. Use: cd multimodal_lm && make docker_build && make docker_run"

# ------------------------------------------------------------------------------
# Docker Compose (Development - all services)
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
# Docker Compose (Cloud - API only, VLM and MLM deployed separately)
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
# Docker Build & Push (VLM Service)
# ------------------------------------------------------------------------------
# Build VLM image (runtime model download via entrypoint, works with all models)
docker_build_vlm:
	cd colpali-vlm && docker build -t colpali-vlm:latest .

# Push VLM image to Docker Hub
docker_push_vlm:
	docker tag colpali-vlm:latest $(DOCKERHUB_USERNAME)/colpali-vlm:latest
	docker push $(DOCKERHUB_USERNAME)/colpali-vlm:latest

# Build VLM image with Docker Buildx and push to Docker Hub
docker_buildx_vlm_push:
	cd colpali-vlm &&  docker buildx build --progress=plain -f .\Dockerfile -t $(DOCKERHUB_USERNAME)/colpali-vlm:latest --push .

# ------------------------------------------------------------------------------
# Docker Build & Push (Multimodal LM Service)
# ------------------------------------------------------------------------------
# Build Multimodal LM image
docker_build_mlm:
	cd multimodal_lm && docker build -t multimodal-lm:latest .

# Push Multimodal LM image to Docker Hub
docker_push_mlm:
	docker tag multimodal-lm:latest $(DOCKERHUB_USERNAME)/multimodal-lm:latest
	docker push $(DOCKERHUB_USERNAME)/multimodal-lm:latest

# Build Multimodal LM image with Docker Buildx and push to Docker Hub
docker_buildx_mlm_push:
	cd multimodal_lm &&  docker buildx build --progress=plain -f .\Dockerfile -t $(DOCKERHUB_USERNAME)/multimodal-lm:latest --push .

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

# Build Document API image with Docker Buildx and push to Docker Hub
docker_buildx_api_push:
	cd document-api &&  docker buildx build --progress=plain -f .\Dockerfile -t $(DOCKERHUB_USERNAME)/document-api:latest --push .

# ------------------------------------------------------------------------------
# Combined Build & Push
# ------------------------------------------------------------------------------
# Build all images
docker_build_all: docker_build_vlm docker_build_mlm docker_build_api

# Push all images to Docker Hub
docker_push_all: docker_push_vlm docker_push_mlm docker_push_api
