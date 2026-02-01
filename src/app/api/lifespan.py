import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, TypedDict

import instructor
from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor
from fastapi import FastAPI
from instructor import AsyncInstructor
from loguru import logger
from qdrant_client import AsyncQdrantClient

from app.api.state import (
    create_anthropic_client,
    create_qdrant_client,
    create_supabase_client,
)
from app.colpali.loaders import ColQwen2_5Loader
from app.services.img_downloader import SupabaseJPEGDownloader
from app.services.img_uploader import SupabaseJPEGUploader
from app.settings import get_settings


class State(TypedDict):
    model: ColQwen2_5
    processor: ColQwen2_5_Processor
    supabase_uploader: SupabaseJPEGUploader
    supabase_downloader: SupabaseJPEGDownloader
    instructor_client: AsyncInstructor
    qdrant_client: AsyncQdrantClient
    collection_name: str
    model_semaphore: asyncio.Semaphore
    qdrant_semaphore: asyncio.Semaphore
    llm_config: dict[str, Any]
    settings: Any


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    startup_start = time.perf_counter()
    logger.info("Application startup initiated")

    logger.info("Loading settings")
    settings = get_settings()

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

    logger.info(
        "Loading ColQwen2.5 model | model={}",
        settings.colpali.colpali_model_name,
    )
    model_start = time.perf_counter()
    loader = ColQwen2_5Loader(model_name=settings.colpali.colpali_model_name)
    model, processor = loader.load()
    model_time = time.perf_counter() - model_start
    logger.info("Model loaded | time_seconds={:.2f}", model_time)

    logger.info("Creating ColPali model semaphore")
    model_semaphore = asyncio.Semaphore(
        settings.colpali.max_concurrent_inferences
    )
    logger.info(
        "ColPali model semaphore created | max_concurrent_inferences={}",
        settings.colpali.max_concurrent_inferences,
    )

    # Create semaphore for Qdrant operations to prevent connection pool exhaustion
    # Allow more concurrent Qdrant queries than model inferences since Qdrant is lighter
    qdrant_max_concurrent = settings.colpali.max_concurrent_inferences * 3
    logger.info("Creating Qdrant semaphore")
    qdrant_semaphore = asyncio.Semaphore(qdrant_max_concurrent)
    logger.info(
        "Qdrant semaphore created | qdrant_max_concurrent_inferences={}",
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
        "Application startup complete | collection={} | startup_time_seconds={:.2f}",
        settings.qdrant.collection_name,
        startup_time,
    )

    yield {
        "model": model,
        "processor": processor,
        "supabase_uploader": supabase_uploader,
        "supabase_downloader": supabase_downloader,
        "instructor_client": instructor_client,
        "qdrant_client": qdrant_client,
        "collection_name": settings.qdrant.collection_name,
        "model_semaphore": model_semaphore,
        "qdrant_semaphore": qdrant_semaphore,
        "llm_config": llm_config,
        "settings": settings,
    }

    logger.info("Application shutdown initiated")
    await qdrant_client.close()
    logger.info("Qdrant client closed")
    await anthropic_client.close()
    logger.info("Anthropic client closed")
    logger.success("Application shutdown complete")
