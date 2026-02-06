import asyncio
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from instructor import AsyncInstructor
from loguru import logger
from qdrant_client import AsyncQdrantClient

from doc_api.services.img_downloader import SupabaseJPEGDownloader
from doc_api.services.img_uploader import SupabaseJPEGUploader
from doc_api.services.vlm_client import VLMClient
from doc_api.settings import Settings
from doc_api.utils.prompt_utils import read_prompt_from_plain_file

security = HTTPBearer(auto_error=False)


async def get_vlm_client(request: Request) -> VLMClient:
    return request.state.vlm_client


async def get_qdrant_client(request: Request) -> AsyncQdrantClient:
    return request.state.qdrant_client


async def get_supabase_uploader(request: Request) -> SupabaseJPEGUploader:
    return request.state.supabase_uploader


async def get_supabase_downloader(request: Request) -> SupabaseJPEGDownloader:
    return request.state.supabase_downloader


async def get_collection_name(request: Request) -> str:
    return request.state.collection_name


async def get_instructor_client(request: Request) -> AsyncInstructor:
    return request.state.instructor_client


async def get_qdrant_semaphore(request: Request) -> asyncio.Semaphore:
    return request.state.qdrant_semaphore


async def get_llm_config(request: Request) -> dict[str, Any]:
    return request.state.llm_config


async def get_settings_from_state(request: Request) -> Settings:
    return request.state.settings


@lru_cache(maxsize=1)
def get_prompts():
    logger.info("Loading prompts (cached)")
    prompt1 = read_prompt_from_plain_file("prompts/response_1")
    prompt2 = read_prompt_from_plain_file("prompts/response_2")
    logger.info(
        "Prompts loaded and cached | prompt1_len={} | prompt2_len={}",
        len(prompt1),
        len(prompt2),
    )
    return {"prompt1": prompt1, "prompt2": prompt2}


async def get_auth_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str | None:
    """Extract the raw JWT token from the Authorization header."""
    if credentials is None:
        return None
    return credentials.credentials
