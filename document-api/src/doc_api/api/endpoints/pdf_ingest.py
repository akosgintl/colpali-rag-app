import asyncio
import gc
import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from pdf2image import convert_from_bytes
from pydantic import UUID4
from qdrant_client import AsyncQdrantClient, models

from doc_api.api.auth import get_current_user
from doc_api.api.dependencies import (
    get_auth_token,
    get_collection_name,
    get_qdrant_client,
    get_qdrant_semaphore,
    get_settings_from_state,
    get_supabase_uploader,
    get_vlm_client,
)
from doc_api.api.rate_limit import get_ingest_rate_limit, limiter
from doc_api.services.img_uploader import SupabaseJPEGUploader
from doc_api.services.vlm_client import VLMClient, VLMClientError
from doc_api.settings import Settings
from doc_api.utils.qdrant_utils import upsert_with_retry

router = APIRouter()


class PDFIngestController:
    def __init__(
        self,
        vlm_client: VLMClient,
        uploader: SupabaseJPEGUploader,
        qdrant_client: AsyncQdrantClient,
        collection_name: str,
        qdrant_semaphore: asyncio.Semaphore,
        settings: Settings,
        auth_token: str | None = None,
    ):
        self.vlm_client = vlm_client
        self.uploader = uploader
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.qdrant_semaphore = qdrant_semaphore
        self.settings = settings
        self.auth_token = auth_token

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

                    try:
                        # Call VLM service for embeddings
                        batch_embeddings = await self.vlm_client.embed_images(
                            batch, auth_token=self.auth_token
                        )
                    except VLMClientError as e:
                        error_msg = f"VLM service error: {str(e)}"
                        logger.error(
                            "VLM inference failed | filename={} | batch={}/{} | error={}",
                            file.filename,
                            batch_idx + 1,
                            total_batches,
                            str(e),
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
                            "session_id": str(session_id),
                            "document": file.filename,
                            "page": page_number,
                        }
                        # Embedding is already a list from VLM service
                        point = models.PointStruct(
                            id=str(uuid4()),
                            vector=embedding,
                            payload=payload,
                        )
                        points.append(point)

                    async with self.qdrant_semaphore:
                        await upsert_with_retry(
                            qdrant_client=self.qdrant_client,
                            collection_name=self.collection_name,
                            points=points,
                            vector_dim=self.settings.qdrant.vector_dim,
                        )

                    await self.uploader.upload_images(
                        session_id=session_id,
                        file_name=file.filename or "unknown",
                        images=batch,
                        start=start_idx + 1,
                    )

                    del batch_embeddings
                    gc.collect()

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
    vlm_client: Annotated[VLMClient, Depends(get_vlm_client)],
    uploader: Annotated[SupabaseJPEGUploader, Depends(get_supabase_uploader)],
    qdrant_client: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
    collection_name: Annotated[str, Depends(get_collection_name)],
    qdrant_semaphore: Annotated[asyncio.Semaphore, Depends(get_qdrant_semaphore)],
    settings: Annotated[Settings, Depends(get_settings_from_state)],
    current_user: Annotated[dict | None, Depends(get_current_user)],
    auth_token: Annotated[str | None, Depends(get_auth_token)],
):
    controller = PDFIngestController(
        vlm_client=vlm_client,
        uploader=uploader,
        qdrant_client=qdrant_client,
        collection_name=collection_name,
        qdrant_semaphore=qdrant_semaphore,
        settings=settings,
        auth_token=auth_token,
    )
    return await controller.ingest(files=files, session_id=session_id)
