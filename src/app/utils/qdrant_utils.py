from loguru import logger
from qdrant_client import AsyncQdrantClient, models
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
    before_sleep=before_sleep_log(logger, "WARNING"),
)
async def upsert_with_retry(
    qdrant_client: AsyncQdrantClient,
    collection_name: str,
    points: list[models.PointStruct],
) -> None:
    logger.debug(
        "Upserting points to Qdrant | collection={} | count={}",
        collection_name,
        len(points),
    )
    try:
        await qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
        )
        logger.debug("Upsert successful | points={}", len(points))
    except Exception as e:
        logger.warning(
            "Upsert failed (will retry) | collection={} | error={}",
            collection_name,
            str(e),
        )
        raise
