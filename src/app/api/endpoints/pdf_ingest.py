import asyncio
import gc
import time
from typing import Annotated
from uuid import uuid4

import torch
from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor
from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from pdf2image import convert_from_bytes
from pydantic import UUID4
from qdrant_client import AsyncQdrantClient, models

from app.api.auth import get_current_user
from app.api.dependencies import (
    get_collection_name,
    get_colpali_model,
    get_colpali_processor,
    get_model_semaphore,
    get_qdrant_client,
    get_qdrant_semaphore,
    get_settings_from_state,
    get_supabase_uploader,
)
from app.api.rate_limit import get_ingest_rate_limit, limiter
from app.services.img_uploader import SupabaseJPEGUploader
from app.settings import Settings
from app.utils.qdrant_utils import upsert_with_retry

router = APIRouter()


class PDFIngestController:
    def __init__(
        self,
        model: ColQwen2_5,
        processor: ColQwen2_5_Processor,
        uploader: SupabaseJPEGUploader,
        qdrant_client: AsyncQdrantClient,
        collection_name: str,
        model_semaphore: asyncio.Semaphore,
        qdrant_semaphore: asyncio.Semaphore,
        settings: Settings,
    ):
        self.model = model
        self.processor = processor
        self.uploader = uploader
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.model_semaphore = model_semaphore
        self.qdrant_semaphore = qdrant_semaphore
        self.settings = settings

    async def ingest(
        self, files: list[UploadFile], session_id: UUID4
    ) -> dict[str, list[dict[str, str | int]]]:
        ingest_start = time.perf_counter()
        logger.info(
            "PDF ingest started | session_id={} | file_count={}",
            session_id,
            len(files),
        )
        results = []
        max_file_size_bytes = (
            self.settings.processing.max_file_size_mb * 1024 * 1024
        )
        max_pages_batch = self.settings.processing.max_pages_per_batch
        max_pdf_pages = self.settings.processing.max_pdf_pages
        clear_interval = self.settings.processing.clear_cuda_cache_interval
        batch_count = 0

        for file in files:
            file_start = time.perf_counter()
            logger.info(
                "Processing file | filename={} | session_id={}",
                file.filename,
                session_id,
            )
            try:
                pdf_bytes = await file.read()
                file_size = len(pdf_bytes)
                logger.info(
                    "PDF read | filename={} | size_bytes={}",
                    file.filename,
                    file_size,
                )

                if file_size > max_file_size_bytes:
                    error_msg = f"File exceeds {self.settings.processing.max_file_size_mb}MB limit"
                    logger.warning(
                        "File size limit exceeded | filename={} | size_mb={:.2f} | limit_mb={}",
                        file.filename,
                        file_size / (1024 * 1024),
                        self.settings.processing.max_file_size_mb,
                    )
                    results.append(
                        {"filename": file.filename, "error": error_msg}
                    )
                    continue

                convert_start = time.perf_counter()
                try:
                    images = await asyncio.wait_for(
                        run_in_threadpool(
                            convert_from_bytes,
                            pdf_file=pdf_bytes,
                            dpi=300,
                            thread_count=4,
                            fmt="jpeg",
                        ),
                        timeout=self.settings.timeout.pdf_conversion_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    error_msg = f"PDF conversion timed out after {self.settings.timeout.pdf_conversion_timeout_seconds}s"
                    logger.error(
                        "PDF conversion timeout | filename={} | timeout_seconds={}",
                        file.filename,
                        self.settings.timeout.pdf_conversion_timeout_seconds,
                    )
                    results.append({"filename": file.filename, "error": error_msg})
                    continue
                convert_time = time.perf_counter() - convert_start
                num_images = len(images)
                logger.info(
                    "PDF converted to images | filename={} | pages={} | time_ms={:.2f}",
                    file.filename,
                    num_images,
                    convert_time * 1000,
                )

                if num_images > max_pdf_pages:
                    error_msg = f"PDF exceeds {max_pdf_pages} page limit"
                    logger.warning(
                        "Page limit exceeded | filename={} | pages={} | limit={}",
                        file.filename,
                        num_images,
                        max_pdf_pages,
                    )
                    results.append(
                        {"filename": file.filename, "error": error_msg}
                    )
                    del images
                    gc.collect()
                    continue

                total_batches = (
                    num_images + max_pages_batch - 1
                ) // max_pages_batch

                for batch_idx, start_idx in enumerate(
                    range(0, num_images, max_pages_batch)
                ):
                    end_idx = start_idx + max_pages_batch
                    batch = images[start_idx:end_idx]
                    batch_count += 1

                    def _run_inference():
                        with torch.inference_mode():
                            processed = self.processor.process_images(batch).to(
                                self.model.device
                            )
                            embeddings = self.model(**processed)
                            return processed, embeddings

                    try:
                        async with self.model_semaphore:
                            processed_images, batch_embeddings = await asyncio.wait_for(
                                run_in_threadpool(_run_inference),
                                timeout=self.settings.timeout.colpali_inference_timeout_seconds,
                            )
                    except asyncio.TimeoutError:
                        error_msg = f"Model inference timed out after {self.settings.timeout.colpali_inference_timeout_seconds}s"
                        logger.error(
                            "Model inference timeout | filename={} | batch={}/{} | timeout_seconds={}",
                            file.filename,
                            batch_idx + 1,
                            total_batches,
                            self.settings.timeout.colpali_inference_timeout_seconds,
                        )
                        results.append(
                            {"filename": file.filename, "error": error_msg}
                        )
                        del batch
                        break

                    points = []
                    for offset, (_, embedding) in enumerate(
                        zip(batch, batch_embeddings)
                    ):
                        page_number = start_idx + offset + 1
                        payload = {
                            "session_id": session_id,
                            "document": file.filename,
                            "page": page_number,
                        }
                        vector = embedding.cpu().float().numpy().tolist()
                        point = models.PointStruct(
                            id=str(uuid4()),
                            vector=vector,
                            payload=payload,
                        )
                        points.append(point)

                    async with self.qdrant_semaphore:
                        await upsert_with_retry(
                            qdrant_client=self.qdrant_client,
                            collection_name=self.collection_name,
                            points=points,
                        )

                    await self.uploader.upload_images(
                        session_id=session_id,
                        file_name=file.filename or "unknown",
                        images=batch,
                        start=start_idx + 1,
                    )

                    del processed_images, batch_embeddings
                    if batch_count % clear_interval == 0:
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        gc.collect()
                        logger.info(
                            "Memory cleared | batch_count={}",
                            batch_count,
                        )

                    logger.info(
                        "Processed batch {batch_num}/{total_batches} for file {filename}",
                        batch_num=batch_idx + 1,
                        total_batches=total_batches,
                        filename=file.filename,
                    )

                del images
                gc.collect()

                file_time = time.perf_counter() - file_start
                logger.info(
                    "File processed successfully | filename={} | pages={} | time_seconds={:.2f}",
                    file.filename,
                    num_images,
                    file_time,
                )
                results.append(
                    {"filename": file.filename, "num_pages": num_images}
                )
            except Exception as e:
                logger.error(
                    "Error processing file | filename={} | session_id={} | error={}",
                    file.filename,
                    session_id,
                    str(e),
                    exc_info=True,
                )
                results.append({"filename": file.filename, "error": str(e)})

        total_time = time.perf_counter() - ingest_start
        logger.info(
            "PDF ingest completed | session_id={} | files={} | total_time_seconds={:.2f}",
            session_id,
            len(files),
            total_time,
        )
        return {"results": results}


@router.post("/ingest-pdfs/")
@limiter.limit(get_ingest_rate_limit)
async def ingest_pdf(
    request: Request,
    files: list[UploadFile],
    session_id: UUID4,
    model: Annotated[ColQwen2_5, Depends(get_colpali_model)],
    processor: Annotated[ColQwen2_5_Processor, Depends(get_colpali_processor)],
    uploader: Annotated[SupabaseJPEGUploader, Depends(get_supabase_uploader)],
    qdrant_client: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
    collection_name: Annotated[str, Depends(get_collection_name)],
    model_semaphore: Annotated[asyncio.Semaphore, Depends(get_model_semaphore)],
    qdrant_semaphore: Annotated[asyncio.Semaphore, Depends(get_qdrant_semaphore)],
    settings: Annotated[Settings, Depends(get_settings_from_state)],
    current_user: Annotated[dict | None, Depends(get_current_user)],
):
    controller = PDFIngestController(
        model=model,
        processor=processor,
        uploader=uploader,
        qdrant_client=qdrant_client,
        collection_name=collection_name,
        model_semaphore=model_semaphore,
        qdrant_semaphore=qdrant_semaphore,
        settings=settings,
    )
    return await controller.ingest(files=files, session_id=session_id)
