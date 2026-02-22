import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, TypedDict

import httpx
from fastapi import FastAPI
from loguru import logger
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from tenacity import (
    retry,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from doc_api.api.state import (
    create_openai_client,
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
    openai_client: AsyncOpenAI
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


async def _check_mlm_health(url: str) -> bool:
    """
    Check if the multimodal LM service is healthy.
    Returns True if healthy, False otherwise.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{url}/health", timeout=10.0)
            return resp.status_code == 200
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    startup_start = time.perf_counter()
    logger.info("Document API startup initiated")

    logger.info("Loading settings")
    settings = get_settings()

    logger.info("Creating VLM client | url={}", settings.vlm.vlm_service_url)
    vlm_client = VLMClient(
        base_url=settings.vlm.vlm_service_url,
        timeout_seconds=settings.vlm.vlm_timeout_seconds,
        api_key=settings.vlm.vlm_api_key or None,
    )

    # Wait for VLM service to become healthy with retry logic
    logger.info("Waiting for VLM service to become ready...")

    @retry(
        retry=retry_if_result(lambda x: not x),  # Retry if result is False
        stop=stop_after_attempt(30),  # 30 attempts
        wait=wait_exponential(
            multiplier=2, min=2, max=30
        ),  # 2s, 4s, 8s, 16s, 30s, ...
        reraise=False,
    )
    async def wait_for_vlm() -> bool:
        return await _wait_for_vlm_health(
            vlm_client, settings.vlm.vlm_service_url
        )

    vlm_healthy = await wait_for_vlm()
    if not vlm_healthy:
        logger.error(
            "VLM service failed to become healthy after retries | url={}",
            settings.vlm.vlm_service_url,
        )
        raise RuntimeError(
            f"VLM service not available at {settings.vlm.vlm_service_url}"
        )

    # Wait for multimodal LM service to become healthy
    mlm_url = settings.multimodal_lm.multimodal_lm_service_url
    logger.info(
        "Waiting for multimodal LM service to become ready... | url={}", mlm_url
    )

    @retry(
        retry=retry_if_result(lambda x: not x),
        stop=stop_after_attempt(30),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=False,
    )
    async def wait_for_mlm() -> bool:
        is_healthy = await _check_mlm_health(mlm_url)
        if is_healthy:
            logger.info("Multimodal LM service is healthy | url={}", mlm_url)
        else:
            logger.warning(
                "Multimodal LM service not ready yet, retrying... | url={}",
                mlm_url,
            )
        return is_healthy

    mlm_healthy = await wait_for_mlm()
    if not mlm_healthy:
        logger.error(
            "Multimodal LM service failed to become healthy after retries | url={}",
            mlm_url,
        )
        raise RuntimeError(f"Multimodal LM service not available at {mlm_url}")

    logger.info("Creating Qdrant client")
    qdrant_client = create_qdrant_client(settings=settings)

    logger.info("Creating OpenAI client for multimodal LM")
    openai_client = create_openai_client(settings=settings)

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
        "model": settings.multimodal_lm.multimodal_lm_model_name,
        "max_tokens": settings.multimodal_lm.multimodal_lm_max_tokens,
        "temperature": settings.multimodal_lm.multimodal_lm_temperature,
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
        "openai_client": openai_client,
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
    await openai_client.close()
    logger.info("OpenAI client closed")
    logger.success("Document API shutdown complete")
