import asyncio
import base64
import time

from loguru import logger
from supabase.client import AsyncClient as SupabaseAsyncClient


class SupabaseJPEGDownloader:
    def __init__(
        self, client: SupabaseAsyncClient, bucket_name: str, timeout_seconds: int = 120
    ):
        self.client = client
        self.bucket_name = bucket_name
        self.timeout_seconds = timeout_seconds
        logger.info(
            "SupabaseJPEGDownloader initialized | bucket={} | timeout={}s",
            bucket_name,
            timeout_seconds,
        )

    async def download_image(self, filename: str) -> bytes:
        logger.info("Downloading image | filename={}", filename)
        try:
            # Wrap download with timeout
            data = await asyncio.wait_for(
                self.client.storage.from_(id=self.bucket_name).download(
                    path=filename
                ),
                timeout=self.timeout_seconds,
            )
            logger.info(
                "Image downloaded | filename={} | size_bytes={}",
                filename,
                len(data),
            )
            return data
        except asyncio.TimeoutError:
            logger.error(
                "Download timeout | filename={} | timeout_seconds={}",
                filename,
                self.timeout_seconds,
            )
            raise
        except Exception as e:
            logger.error(
                "Failed to download image | filename={} | error={}",
                filename,
                str(e),
            )
            raise

    async def download_images(self, paths: list[str]) -> list[bytes]:
        start_time = time.perf_counter()
        logger.info("Downloading {} images in parallel", len(paths))
        tasks = [self.download_image(path) for path in paths]
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start_time
        logger.info(
            "Downloaded {} images | time_ms={:.2f}",
            len(results),
            elapsed * 1000,
        )
        return results

    async def download_base64_images(
        self, filenames: list[str]
    ) -> list[str]:
        """Download images and return as base64-encoded JPEG strings."""
        logger.info(
            "Converting {} images to base64 format", len(filenames)
        )
        images_bytes = await self.download_images(paths=filenames)
        return [
            base64.b64encode(img_bytes).decode("utf-8")
            for img_bytes in images_bytes
        ]
