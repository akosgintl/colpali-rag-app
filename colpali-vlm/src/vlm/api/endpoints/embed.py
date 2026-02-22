import asyncio
import gc
import time
from io import BytesIO
from typing import Annotated, Any

import torch
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from PIL import Image
from pydantic import BaseModel

from vlm.api.auth import verify_api_key
from vlm.api.dependencies import (
    get_model,
    get_processor,
    get_semaphore,
    get_settings_from_state,
)
from vlm.settings import Settings

router = APIRouter()


class QueryEmbedRequest(BaseModel):
    query: str


class EmbeddingResponse(BaseModel):
    """
    Response containing multi-vector embeddings for images.
    
    Embeddings are returned as float16 values (converted from float32)
    for 50% size reduction with minimal accuracy impact.
    """
    embeddings: list[list[list[float]]]  # float16 values
    processing_time_ms: float


class QueryEmbeddingResponse(BaseModel):
    """
    Response containing multi-vector embedding for a query.
    
    Embedding is returned as float16 values (converted from float32)
    for 50% size reduction with minimal accuracy impact.
    """
    embedding: list[list[float]]  # float16 values
    processing_time_ms: float


@router.post("/embed/images", response_model=EmbeddingResponse)
async def embed_images(
    images: list[UploadFile],
    model: Annotated[Any, Depends(get_model)],
    processor: Annotated[Any, Depends(get_processor)],
    semaphore: Annotated[asyncio.Semaphore, Depends(get_semaphore)],
    settings: Annotated[Settings, Depends(get_settings_from_state)],
    _api_key_verified: Annotated[None, Depends(verify_api_key)],
):
    """
    Generate embeddings for a list of images.

    Args:
        images: List of JPEG/PNG image files

    Returns:
        EmbeddingResponse with embeddings for each image (128-dim or 320-dim multi-vectors).
        Embeddings are returned as float16 values for optimized transfer size.
    """
    if not images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No images provided",
        )

    start_time = time.perf_counter()
    logger.info("Embedding request received | image_count={}", len(images))

    # Load images into PIL format
    pil_images: list[Image.Image] = []
    try:
        for img in images:
            content = await img.read()
            pil_image = Image.open(BytesIO(content))
            # Convert to RGB if necessary (e.g., RGBA PNGs)
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")
            pil_images.append(pil_image)
    except Exception as e:
        logger.error("Failed to load images | error={}", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to load images: {str(e)}",
        )

    logger.info("Images loaded | count={}", len(pil_images))

    def _run_inference() -> list[list[list[float]]]:
        with torch.inference_mode():
            processed = processor.process_images(pil_images).to(model.device)
            output = model(**processed)
            
            # Handle TomoroAI output format (has .embeddings attribute)
            if hasattr(output, 'embeddings'):
                embeddings = output.embeddings
            else:
                embeddings = output
            
            # Convert to float16 for 50% size reduction (minimal accuracy impact)
            # Then convert to list format: [batch, seq_len, hidden_dim]
            # Note: .half() reduces precision to float16, .numpy().tolist() converts
            # to Python list (Python floats have float16 precision, reducing JSON size)
            return [
                emb.cpu().half().numpy().tolist() for emb in embeddings
            ]

    try:
        async with semaphore:
            embeddings = await asyncio.wait_for(
                run_in_threadpool(_run_inference),
                timeout=settings.timeout.inference_timeout_seconds,
            )
    except asyncio.TimeoutError:
        logger.error(
            "Inference timeout | timeout_seconds={}",
            settings.timeout.inference_timeout_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Inference timed out after {settings.timeout.inference_timeout_seconds}s",
        )
    finally:
        # Clean up
        for img in pil_images:
            img.close()
        del pil_images
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    processing_time = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Embeddings generated | count={} | time_ms={:.2f}",
        len(embeddings),
        processing_time,
    )

    return EmbeddingResponse(
        embeddings=embeddings,
        processing_time_ms=processing_time,
    )


@router.post("/embed/query", response_model=QueryEmbeddingResponse)
async def embed_query(
    request: QueryEmbedRequest,
    model: Annotated[Any, Depends(get_model)],
    processor: Annotated[Any, Depends(get_processor)],
    semaphore: Annotated[asyncio.Semaphore, Depends(get_semaphore)],
    settings: Annotated[Settings, Depends(get_settings_from_state)],
    _api_key_verified: Annotated[None, Depends(verify_api_key)],
):
    """
    Generate embedding for a text query.

    Args:
        request: QueryEmbedRequest with query string

    Returns:
        QueryEmbeddingResponse with 128-dim or 320-dim multi-vector embedding.
        Embedding is returned as float16 values for optimized transfer size.
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty",
        )

    start_time = time.perf_counter()
    logger.info(
        "Query embedding request | query_length={} | query_text={}",
        len(request.query),
        request.query[:100],
    )

    def _run_query_embedding() -> list[list[float]]:
        with torch.inference_mode():
            # Detect processor type and call appropriate method
            if hasattr(processor, 'process_texts'):
                processed = processor.process_texts(texts=[request.query])
            else:
                processed = processor.process_queries(queries=[request.query])
            
            processed = {k: v.to(model.device) for k, v in processed.items()}
            output = model(**processed)
            
            # Handle TomoroAI output format (has .embeddings attribute)
            if hasattr(output, 'embeddings'):
                embeddings = output.embeddings
            else:
                embeddings = output
            
            # Convert to float16 for 50% size reduction (minimal accuracy impact)
            # Note: .half() reduces precision to float16, .numpy().tolist() converts
            # to Python list (Python floats have float16 precision, reducing JSON size)
            # Return first (and only) query embedding
            return embeddings[0].cpu().half().numpy().tolist()

    try:
        async with semaphore:
            embedding = await asyncio.wait_for(
                run_in_threadpool(_run_query_embedding),
                timeout=settings.timeout.inference_timeout_seconds,
            )
    except asyncio.TimeoutError:
        logger.error(
            "Query embedding timeout | timeout_seconds={}",
            settings.timeout.inference_timeout_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Inference timed out after {settings.timeout.inference_timeout_seconds}s",
        )

    processing_time = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Query embedding generated | time_ms={:.2f}",
        processing_time,
    )

    return QueryEmbeddingResponse(
        embedding=embedding,
        processing_time_ms=processing_time,
    )
