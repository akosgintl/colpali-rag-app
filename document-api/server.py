from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from doc_api.api.endpoints import pdf_ingest, query
from doc_api.api.lifespan import lifespan
from doc_api.api.middleware import TimeoutMiddleware
from doc_api.api.rate_limit import limiter
from doc_api.logging_config import configure_logging
from doc_api.settings import get_settings

configure_logging()
logger.info("Starting document-api server")

settings = get_settings()

app = FastAPI(
    title="Document API",
    description="Document ingestion and query API with VLM-powered retrieval",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    TimeoutMiddleware,
    endpoint_timeouts={
        "/ingest-pdfs/": settings.timeout.ingest_endpoint_timeout_seconds,
        "/query/": settings.timeout.query_endpoint_timeout_seconds,
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.auth.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(pdf_ingest.router)
app.include_router(query.router)


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}
