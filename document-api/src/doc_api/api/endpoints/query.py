import asyncio
import time
from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from instructor import AsyncInstructor
from loguru import logger
from pydantic import UUID4
from qdrant_client import AsyncQdrantClient, models

from doc_api.api.auth import get_current_user
from doc_api.api.dependencies import (
    get_auth_token,
    get_collection_name,
    get_instructor_client,
    get_llm_config,
    get_prompts,
    get_qdrant_client,
    get_qdrant_semaphore,
    get_settings_from_state,
    get_supabase_downloader,
    get_vlm_client,
)
from doc_api.api.rate_limit import get_query_rate_limit, limiter
from doc_api.models.query_response import FinalResponse
from doc_api.services.img_downloader import SupabaseJPEGDownloader
from doc_api.services.vlm_client import VLMClient, VLMClientError
from doc_api.settings import Settings

router = APIRouter()


class QueryController:
    def __init__(
        self,
        vlm_client: VLMClient,
        downloader: SupabaseJPEGDownloader,
        instructor_client: AsyncInstructor,
        qdrant_client: AsyncQdrantClient,
        collection_name: str,
        prompts: dict[str, str],
        qdrant_semaphore: asyncio.Semaphore,
        llm_config: dict[str, Any],
        settings: Settings,
        auth_token: str | None = None,
    ) -> None:
        self.vlm_client = vlm_client
        self.downloader = downloader
        self.instructor_client = instructor_client
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.prompts = prompts
        self.qdrant_semaphore = qdrant_semaphore
        self.llm_config = llm_config
        self.settings = settings
        self.auth_token = auth_token

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

        # Create generator with timeout enforcement
        generator = self._process_query(query, top_k, session_id, request_start)
        timeout = self.settings.timeout.query_endpoint_timeout_seconds

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        generator.__anext__(),
                        timeout=timeout,
                    )
                    yield chunk
                except StopAsyncIteration:
                    break
        except asyncio.TimeoutError:
            logger.error(
                "Query endpoint timeout | session_id={} | timeout_seconds={}",
                session_id,
                timeout,
            )
            # Close the generator to clean up resources
            await generator.aclose()
            # Yield error message as final chunk
            error_response = {
                "references": [],
                "answer": f"Query timed out after {timeout} seconds",
            }
            yield FinalResponse(**error_response).model_dump_json() + "\n"
        except Exception:
            # Ensure generator is closed on any other exception
            await generator.aclose()
            raise

    async def _process_query(
        self, query: str, top_k: int, session_id: UUID4, request_start: float
    ) -> AsyncIterator[Any]:
        embed_start = time.perf_counter()

        try:
            # Call VLM service for query embedding
            query_embedding = await self.vlm_client.embed_query(
                query, auth_token=self.auth_token
            )
        except VLMClientError as e:
            logger.error(
                "VLM query embedding failed | session_id={} | error={}",
                session_id,
                str(e),
            )
            raise

        embed_time = time.perf_counter() - embed_start
        logger.info(
            "Query embedding generated | time_ms={:.2f}", embed_time * 1000
        )

        search_start = time.perf_counter()
        async with self.qdrant_semaphore:
            search_results = await self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
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
        logger.info(
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
            async with self.qdrant_semaphore:
                diagnostic_results = await self.qdrant_client.query_points(
                    collection_name=self.collection_name,
                    query=query_embedding,
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
        logger.info(
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
            model=self.llm_config["model"],
            response_model=FinalResponse,
            messages=[{"role": "user", "content": query_content}],  # type: ignore
            context={"query": query},
            temperature=self.llm_config["temperature"],
            max_tokens=self.llm_config["max_tokens"],
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
@limiter.limit(get_query_rate_limit)
async def query_endpoint(
    request: Request,
    query: str,
    top_k: int,
    session_id: UUID4,
    vlm_client: Annotated[VLMClient, Depends(get_vlm_client)],
    downloader: Annotated[
        SupabaseJPEGDownloader, Depends(get_supabase_downloader)
    ],
    instructor_client: Annotated[
        AsyncInstructor, Depends(get_instructor_client)
    ],
    qdrant_client: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
    collection_name: Annotated[str, Depends(get_collection_name)],
    prompts: Annotated[dict[str, str], Depends(get_prompts)],
    qdrant_semaphore: Annotated[asyncio.Semaphore, Depends(get_qdrant_semaphore)],
    llm_config: Annotated[dict[str, Any], Depends(get_llm_config)],
    settings: Annotated[Settings, Depends(get_settings_from_state)],
    current_user: Annotated[dict | None, Depends(get_current_user)],
    auth_token: Annotated[str | None, Depends(get_auth_token)],
):
    controller = QueryController(
        vlm_client=vlm_client,
        downloader=downloader,
        instructor_client=instructor_client,
        qdrant_client=qdrant_client,
        collection_name=collection_name,
        prompts=prompts,
        qdrant_semaphore=qdrant_semaphore,
        llm_config=llm_config,
        settings=settings,
        auth_token=auth_token,
    )
    return StreamingResponse(
        controller.query(query, top_k, session_id),
        media_type="text/event-stream",
    )
