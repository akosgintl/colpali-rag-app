import asyncio
from typing import Any

from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor
from fastapi import Request

from vlm.settings import Settings


async def get_model(request: Request) -> ColQwen2_5:
    return request.state.model


async def get_processor(request: Request) -> ColQwen2_5_Processor:
    return request.state.processor


async def get_semaphore(request: Request) -> asyncio.Semaphore:
    return request.state.model_semaphore


async def get_device(request: Request) -> str:
    return request.state.device


async def get_model_name(request: Request) -> str:
    return request.state.model_name


async def get_settings_from_state(request: Request) -> Settings:
    return request.state.settings
