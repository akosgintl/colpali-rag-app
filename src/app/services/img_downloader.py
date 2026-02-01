import asyncio
import base64
import time

import instructor
from loguru import logger
from supabase.client import AsyncClient as SupabaseAsyncClient


class SupabaseJPEGDownloader:
    def __init__(self, client: SupabaseAsyncClient, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
        logger.debug("SupabaseJPEGDownloader initialized | bucket={}", bucket_name)

    async def download_image(self, filename: str) -> bytes:
        logger.debug("Downloading image | filename={}", filename)
        try:
            data = await self.client.storage.from_(id=self.bucket_name).download(
                path=filename
            )
            logger.debug(
                "Image downloaded | filename={} | size_bytes={}", filename, len(data)
            )
            return data
        except Exception as e:
            logger.error("Failed to download image | filename={} | error={}", filename, str(e))
            raise

    async def download_images(self, paths: list[str]) -> list[bytes]:
        start_time = time.perf_counter()
        logger.info("Downloading {} images in parallel", len(paths))
        tasks = [self.download_image(path) for path in paths]
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start_time
        logger.info("Downloaded {} images | time_ms={:.2f}", len(results), elapsed * 1000)
        return results

    async def download_instructor_images(
        self, filenames: list[str]
    ) -> list[instructor.Image]:
        logger.debug("Converting {} images to instructor format", len(filenames))
        images_bytes = await self.download_images(paths=filenames)
        return bytes_list_to_instructor_images(images_bytes=images_bytes)


def bytes_to_instructor_image(image_bytes: bytes) -> instructor.Image:
    base64_str = base64.b64encode(image_bytes).decode("utf-8")
    return instructor.Image.from_raw_base64(base64_str)


def bytes_list_to_instructor_images(
    images_bytes: list[bytes],
) -> list[instructor.Image]:
    return [
        bytes_to_instructor_image(image_bytes=img_bytes)
        for img_bytes in images_bytes
    ]
