import httpx
from loguru import logger
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from supabase.client import AsyncClient as SupabaseAsyncClient, AsyncClientOptions

from doc_api.settings import Settings


def create_qdrant_client(settings: Settings) -> AsyncQdrantClient:
    logger.info(
        "Initializing AsyncQdrantClient | url={} | timeout={}s",
        settings.qdrant.qdrant_url,
        settings.timeout.qdrant_timeout_seconds,
    )

    # Configure httpx limits for connection pooling
    # This prevents overwhelming Qdrant with too many concurrent connections
    limits = httpx.Limits(
        max_connections=20,  # Total connection pool size
        max_keepalive_connections=10,  # Keepalive connections
    )

    return AsyncQdrantClient(
        url=settings.qdrant.qdrant_url,
        api_key=settings.qdrant.qdrant_api_key,
        timeout=settings.timeout.qdrant_timeout_seconds,
        limits=limits,
    )


def create_supabase_client(settings: Settings) -> SupabaseAsyncClient:
    logger.info(
        "Initializing SupabaseAsyncClient | url={} | timeout={}s",
        settings.supabase.supabase_url,
        settings.timeout.supabase_timeout_seconds,
    )

    # Configure httpx client with timeout for Supabase API
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(float(settings.timeout.supabase_timeout_seconds)),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )

    # Create ClientOptions with proper configuration
    options = AsyncClientOptions(
        headers={"apikey": settings.supabase.supabase_key},
        httpx_client=http_client,
        storage_client_timeout=settings.timeout.supabase_timeout_seconds,
    )
    return SupabaseAsyncClient(
        supabase_key=settings.supabase.supabase_key,
        supabase_url=settings.supabase.supabase_url,
        options=options,
    )


def create_openai_client(settings: Settings) -> AsyncOpenAI:
    logger.info(
        "Initializing AsyncOpenAI client | base_url={} | timeout={}s",
        settings.multimodal_lm.multimodal_lm_service_url,
        settings.timeout.multimodal_lm_timeout_seconds,
    )

    return AsyncOpenAI(
        base_url=f"{settings.multimodal_lm.multimodal_lm_service_url}/v1",
        api_key="not-needed",
        timeout=float(settings.timeout.multimodal_lm_timeout_seconds),
        max_retries=0,
    )
