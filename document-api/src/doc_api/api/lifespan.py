import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, TypedDict

import instructor
from fastapi import FastAPI
from instructor import AsyncInstructor
from loguru import logger
from qdrant_client import AsyncQdrantClient
from tenacity import (
    retry,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from doc_api.api.state import (
    create_anthropic_client,
    create_qdrant_client,
    create_supabase_client,
)
from doc_api.services.img_downloader import SupabaseJPEGDownloader
from doc_api.services.img_uploader import SupabaseJPEGUploader
from doc_api.services.vlm_client import VLMClient
from doc_api.settings import get_settings


class State(TypedDict):
    vlm_client: VLMClient
    supabase_uploader: SupabaseJPEGUploader
    supabase_downloader: SupabaseJPEGDownloader
    instructor_client: AsyncInstructor
    qdrant_client: AsyncQdrantClient
    collection_name: str
    qdrant_semaphore: asyncio.Semaphore
    llm_config: dict[str, Any]
    settings: Any


async def _wait_for_vlm_health(vlm_client: VLMClient, url: str) -> bool:
    """
    Wait for VLM service to become healthy with retry logic.
    Returns True if healthy, False otherwise.
    """
    is_healthy = await vlm_client.health_check()
    if is_healthy:
        logger.info("VLM service is healthy | url={}", url)
    else:
        logger.warning("VLM service not ready yet, retrying... | url={}", url)
    return is_healthy


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    startup_start = time.perf_counter()
    logger.info("Document API startup initiated")

    logger.info("Loading settings")
    settings = get_settings()

    logger.info(
        "Creating VLM client | url={}", settings.vlm.vlm_service_url
    )
    vlm_client = VLMClient(
        base_url=settings.vlm.vlm_service_url,
        timeout_seconds=settings.vlm.vlm_timeout_seconds,
    )

    # Wait for VLM service to become healthy with retry logic
    logger.info("Waiting for VLM service to become ready...")
    
    @retry(
        retry=retry_if_result(lambda x: not x),  # Retry if result is False
        stop=stop_after_attempt(30),  # 30 attempts
        wait=wait_exponential(multiplier=2, min=2, max=30),  # 2s, 4s, 8s, 16s, 30s, ...
        reraise=False,
    )
    async def wait_for_vlm() -> bool:
        return await _wait_for_vlm_health(vlm_client, settings.vlm.vlm_service_url)
    
    vlm_healthy = await wait_for_vlm()
    if not vlm_healthy:
        logger.error(
            "VLM service failed to become healthy after retries | url={}",
            settings.vlm.vlm_service_url,
        )
        raise RuntimeError(
            f"VLM service not available at {settings.vlm.vlm_service_url}"
        )

    logger.info("Creating Qdrant client")
    qdrant_client = create_qdrant_client(settings=settings)

    logger.info("Creating Anthropic client")
    anthropic_client = create_anthropic_client(settings=settings)
    logger.info("Creating Instructor client")
    instructor_client = instructor.from_anthropic(client=anthropic_client)

    logger.info(
        "Creating Supabase client | bucket={}", settings.supabase.bucket
    )
    supabase_client = create_supabase_client(settings=settings)
    logger.info("Creating Supabase uploader")
    supabase_uploader = SupabaseJPEGUploader(
        client=supabase_client,
        bucket_name=settings.supabase.bucket,
        timeout_seconds=settings.timeout.supabase_timeout_seconds,
    )
    logger.info("Creating Supabase downloader")
    supabase_downloader = SupabaseJPEGDownloader(
        client=supabase_client,
        bucket_name=settings.supabase.bucket,
        timeout_seconds=settings.timeout.supabase_timeout_seconds,
    )

    # Create semaphore for Qdrant operations to prevent connection pool exhaustion
    qdrant_max_concurrent = 10
    logger.info("Creating Qdrant semaphore")
    qdrant_semaphore = asyncio.Semaphore(qdrant_max_concurrent)
    logger.info(
        "Qdrant semaphore created | qdrant_max_concurrent={}",
        qdrant_max_concurrent,
    )

    logger.info("Loading LLM config")
    llm_config = {
        "model": settings.anthropic.default_model,
        "max_tokens": settings.anthropic.max_tokens,
        "temperature": settings.anthropic.temperature,
    }
    logger.info("LLM config loaded | model={}", llm_config["model"])

    startup_time = time.perf_counter() - startup_start
    logger.success(
        "Document API startup complete | collection={} | startup_time_seconds={:.2f}",
        settings.qdrant.collection_name,
        startup_time,
    )

    yield {
        "vlm_client": vlm_client,
        "supabase_uploader": supabase_uploader,
        "supabase_downloader": supabase_downloader,
        "instructor_client": instructor_client,
        "qdrant_client": qdrant_client,
        "collection_name": settings.qdrant.collection_name,
        "qdrant_semaphore": qdrant_semaphore,
        "llm_config": llm_config,
        "settings": settings,
    }

    logger.info("Document API shutdown initiated")
    await vlm_client.close()
    logger.info("VLM client closed")
    await qdrant_client.close()
    logger.info("Qdrant client closed")
    await anthropic_client.close()
    logger.info("Anthropic client closed")
    logger.success("Document API shutdown complete")
