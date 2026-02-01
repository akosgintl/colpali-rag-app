import logging

from loguru import logger
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


async def ensure_collection_exists(
    qdrant_client: AsyncQdrantClient,
    collection_name: str,
) -> None:
    """Ensure the collection exists, create it if it doesn't."""
    try:
        collections_response = await qdrant_client.get_collections()
        collections = [
            collection.name for collection in collections_response.collections
        ]

        if collection_name not in collections:
            logger.warning(
                "Collection does not exist, creating it | collection={}",
                collection_name,
            )
            await qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=128,
                    distance=models.Distance.COSINE,
                    multivector_config=models.MultiVectorConfig(
                        comparator=models.MultiVectorComparator.MAX_SIM
                    ),
                    on_disk=False,
                ),
                on_disk_payload=False,
            )

            # Create index on session_id for faster filtering
            await qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name="session_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            logger.info(
                "Collection created successfully | collection={}",
                collection_name,
            )
        else:
            logger.info(
                "Collection already exists | collection={}", collection_name
            )
    except UnexpectedResponse as e:
        logger.error(
            "Failed to check/create collection | collection={} | error={}",
            collection_name,
            str(e),
        )
        raise
    except Exception as e:
        logger.error(
            "Unexpected error checking collection | collection={} | error={}",
            collection_name,
            str(e),
        )
        raise


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def upsert_with_retry(
    qdrant_client: AsyncQdrantClient,
    collection_name: str,
    points: list[models.PointStruct],
) -> None:
    logger.info(
        "Upserting points to Qdrant | collection={} | count={}",
        collection_name,
        len(points),
    )
    try:
        # Ensure collection exists before upserting
        await ensure_collection_exists(qdrant_client, collection_name)

        # Now perform the upsert
        result = await qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
        )
        logger.info(
            "Upsert successful | points={} | result={}", len(points), result
        )
    except UnexpectedResponse as e:
        logger.warning(
            "Upsert failed (will retry) | collection={} | error={} | status={}",
            collection_name,
            str(e),
            getattr(e, "status_code", "unknown"),
        )
        raise
    except Exception as e:
        logger.warning(
            "Upsert failed (will retry) | collection={} | error={} | error_type={}",
            collection_name,
            str(e),
            type(e).__name__,
        )
        raise
