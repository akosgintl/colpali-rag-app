.PHONY: clean-pycache clean-ruff-cache clean-mypy-cache clean-all \
        lint format imports mypy pretty all dev prod \
        docker_build docker_run docker_logs docker_stop \
        docker_push

include .env

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
# Code Quality and Formatting Targets
# ------------------------------------------------------------------------------
lint:
	uv run ruff check src/* --fix
	uv run ruff check server.py --fix

format:
	uv run ruff format src/*
	uv run ruff format server.py

imports:
	uv run ruff check src/* --select I --fix
	uv run ruff check server.py --select I --fix

mypy:
	uv run mypy src server.py

pretty: lint format imports

all: pretty mypy clean-all

# ------------------------------------------------------------------------------
# Run Targets
# ------------------------------------------------------------------------------
dev:
	uv run uvicorn server:app \
		--host 0.0.0.0 \
		--port 8000 \
		--reload

prod:
	uv run uvicorn server:app \
		--host 0.0.0.0 \
		--port 8000 \
		--workers 1

# ------------------------------------------------------------------------------
# Docker
# ------------------------------------------------------------------------------
docker_build:
	docker build -t colpali-vlm:latest .

docker_run:
	docker run --rm --name colpali_vlm \
		--gpus all \
		--env-file .env \
		-p 8000:8000 \
		-d colpali-vlm:latest

docker_logs:
	docker logs -f --tail=100 colpali_vlm

docker_stop:
	docker stop colpali_vlm

docker_push:
	docker tag colpali-vlm:latest $(DOCKERHUB_USERNAME)/colpali-vlm:latest
	docker push $(DOCKERHUB_USERNAME)/colpali-vlm:latest
