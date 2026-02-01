import time
from typing import Annotated, Any, AsyncIterator

import torch
from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from instructor import AsyncInstructor
from loguru import logger
from pydantic import UUID4
from qdrant_client import AsyncQdrantClient, models

from app.api.dependencies import (
    get_collection_name,
    get_colpali_model,
    get_colpali_processor,
    get_instructor_client,
    get_prompts,
    get_qdrant_client,
    get_supabase_downloader,
)
from app.models.query_response import FinalResponse
from app.services.img_downloader import SupabaseJPEGDownloader

router = APIRouter()


class QueryController:
    def __init__(
        self,
        model: ColQwen2_5,
        processor: ColQwen2_5_Processor,
        downloader: SupabaseJPEGDownloader,
        instructor_client: AsyncInstructor,
        qdrant_client: AsyncQdrantClient,
        collection_name: str,
        prompts: dict[str, str],
    ) -> None:
        self.model = model
        self.processor = processor
        self.downloader = downloader
        self.instructor_client = instructor_client
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.prompts = prompts

    async def query(
        self, query: str, top_k: int, session_id: UUID4
    ) -> AsyncIterator[Any]:
        request_start = time.perf_counter()
        logger.info(
            "Query received | session_id={} | top_k={} | query_length={} | query_text={}",
            session_id,
            top_k,
            len(query),
            query[:200],
        )

        embed_start = time.perf_counter()
        with torch.inference_mode():
            processed_queries = self.processor.process_queries(
                queries=[query]
            ).to(self.model.device)
            query_embeddings = self.model(**processed_queries)
        embed_time = time.perf_counter() - embed_start
        logger.debug("Query embedding generated | time_ms={:.2f}", embed_time * 1000)

        search_start = time.perf_counter()
        search_results = await self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_embeddings[0].cpu().float().tolist(),
            limit=top_k,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="session_id",
                        match=models.MatchValue(value=str(session_id)),
                    )
                ]
            ),
            search_params=models.SearchParams(hnsw_ef=128, exact=False),
        )
        search_time = time.perf_counter() - search_start
        logger.debug(
            "Qdrant search completed | results={} | time_ms={:.2f}",
            len(search_results.points),
            search_time * 1000,
        )

        if not search_results.points:
            logger.warning(
                "No search results found | session_id={} | query={}",
                session_id,
                query[:100],
            )
            
            # Diagnostic: Try searching without session_id filter to see if there's any data
            diagnostic_results = await self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_embeddings[0].cpu().float().tolist(),
                limit=1,
                search_params=models.SearchParams(hnsw_ef=128, exact=False),
            )
            logger.info(
                "Diagnostic search without filter | total_points_found={}",
                len(diagnostic_results.points),
            )
            if diagnostic_results.points:
                sample_payload = diagnostic_results.points[0].payload
                logger.info(
                    "Sample point from collection | session_id={} | document={}",
                    sample_payload.get("session_id"),
                    sample_payload.get("document"),
                )

        points = [point.payload for point in search_results.points]
        filenames = [
            f"{point['session_id']}/{point['document']}/{point['page']}.jpeg"
            for point in points
            if point
        ]

        download_start = time.perf_counter()
        instructor_images = await self.downloader.download_instructor_images(
            filenames=filenames
        )
        download_time = time.perf_counter() - download_start
        logger.debug(
            "Images downloaded | count={} | time_ms={:.2f}",
            len(instructor_images),
            download_time * 1000,
        )

        prompt_1 = self.prompts["prompt1"]
        prompt_2 = self.prompts["prompt2"]

        query_content: list[str | object] = [prompt_1]
        for filename, image in zip(filenames, instructor_images):
            query_content.extend(
                [f'\t<image file="{filename}">', image, "\t</image>"]
            )
        query_content.append(prompt_2)

        logger.info(
            "Starting LLM streaming | session_id={} | images={}",
            session_id,
            len(instructor_images),
        )

        stream = self.instructor_client.completions.create_partial(
            model="claude-3-7-sonnet-latest",
            response_model=FinalResponse,
            messages=[{"role": "user", "content": query_content}],  # type: ignore
            context={"query": query},
            temperature=0.0,
            max_tokens=8192,
            max_retries=3,
        )

        chunk_count = 0
        async for partial in stream:
            chunk_count += 1
            yield partial.model_dump_json() + "\n"

        total_time = time.perf_counter() - request_start
        logger.info(
            "Query completed | session_id={} | chunks={} | total_time_ms={:.2f}",
            session_id,
            chunk_count,
            total_time * 1000,
        )


@router.post("/query/")
async def query_endpoint(
    query: str,
    top_k: int,
    session_id: UUID4,
    model: Annotated[ColQwen2_5, Depends(get_colpali_model)],
    processor: Annotated[ColQwen2_5_Processor, Depends(get_colpali_processor)],
    downloader: Annotated[
        SupabaseJPEGDownloader, Depends(get_supabase_downloader)
    ],
    instructor_client: Annotated[
        AsyncInstructor, Depends(get_instructor_client)
    ],
    qdrant_client: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
    collection_name: Annotated[str, Depends(get_collection_name)],
    prompts: Annotated[dict[str, str], Depends(get_prompts)],
):
    controller = QueryController(
        model=model,
        processor=processor,
        downloader=downloader,
        instructor_client=instructor_client,
        qdrant_client=qdrant_client,
        collection_name=collection_name,
        prompts=prompts,
    )
    return StreamingResponse(
        controller.query(query, top_k, session_id),
        media_type="text/event-stream",
    )
