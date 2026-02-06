import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, TypedDict

from fastapi import FastAPI
from loguru import logger

from vlm.colpali.loaders import get_loader
from vlm.settings import get_settings


class State(TypedDict):
    model: Any
    processor: Any
    model_semaphore: asyncio.Semaphore
    device: str
    model_name: str
    model_type: str
    settings: Any


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    startup_start = time.perf_counter()
    logger.info("VLM service startup initiated")

    logger.info("Loading settings")
    settings = get_settings()

    logger.info(
        "Loading ColPali model | type={} | model={}",
        settings.colpali.colpali_model_type,
        settings.colpali.colpali_model_name,
    )
    model_start = time.perf_counter()
    loader = get_loader(
        model_type=settings.colpali.colpali_model_type,
        model_name=settings.colpali.colpali_model_name,
    )
    model, processor = loader.load()
    model_time = time.perf_counter() - model_start
    logger.info("Model loaded | time_seconds={:.2f}", model_time)

    logger.info("Creating model semaphore")
    model_semaphore = asyncio.Semaphore(
        settings.colpali.max_concurrent_inferences
    )
    logger.info(
        "Model semaphore created | max_concurrent_inferences={}",
        settings.colpali.max_concurrent_inferences,
    )

    startup_time = time.perf_counter() - startup_start
    logger.success(
        "VLM service startup complete | device={} | startup_time_seconds={:.2f}",
        loader.device,
        startup_time,
    )

    yield {
        "model": model,
        "processor": processor,
        "model_semaphore": model_semaphore,
        "device": loader.device,
        "model_name": settings.colpali.colpali_model_name,
        "model_type": settings.colpali.colpali_model_type,
        "settings": settings,
    }

    logger.info("VLM service shutdown initiated")
    logger.success("VLM service shutdown complete")
