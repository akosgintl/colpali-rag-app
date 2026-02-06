from fastapi import FastAPI, Request, Response
from loguru import logger

from vlm.api.endpoints import embed
from vlm.api.lifespan import lifespan
from vlm.logging_config import configure_logging
from vlm.settings import get_settings

configure_logging()
logger.info("Starting colpali-vlm service")

settings = get_settings()

app = FastAPI(
    title="ColPali VLM Service",
    description="Vision Language Model embedding service using ColQwen2.5",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(embed.router)


@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint for container orchestration."""
    # Check if model is actually loaded by verifying state exists
    try:
        model = request.state.model
        model_loaded = model is not None
    except AttributeError:
        # State not yet populated (lifespan hasn't completed)
        model_loaded = False
    
    if not model_loaded:
        return Response(
            content='{"status": "unhealthy", "model_loaded": false}',
            status_code=503,
            media_type="application/json"
        )
    
    return {
        "status": "healthy",
        "model_loaded": True,
    }


@app.get("/health/detailed")
async def detailed_health_check(request: Request):
    """Detailed health check with model info."""
    return {
        "status": "healthy",
        "model_loaded": True,
        "device": request.state.device,
        "model_name": request.state.model_name,
    }
