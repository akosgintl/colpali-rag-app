import asyncio
import time
from io import BytesIO

from loguru import logger
from PIL import Image
from pydantic import UUID4
from supabase.client import AsyncClient as SupabaseAsyncClient


class SupabaseJPEGUploader:
    def __init__(self, client: SupabaseAsyncClient, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
        logger.debug("SupabaseJPEGUploader initialized | bucket={}", bucket_name)

    async def _upload_image(
        self, session_id: UUID4, file_name: str, page: int, image: Image.Image
    ):
        path = f"{session_id}/{file_name}/{page}.jpeg"
        logger.debug("Uploading image | path={}", path)
        try:
            with BytesIO() as buffer:
                image.save(buffer, format="JPEG")
                data = buffer.getvalue()
                await self.client.storage.from_(id=self.bucket_name).upload(
                    path=path,
                    file=data,
                    file_options={"content-type": "image/jpeg"},
                )
            logger.debug("Image uploaded | path={} | size_bytes={}", path, len(data))
        except Exception as e:
            logger.error("Failed to upload image | path={} | error={}", path, str(e))
            raise

    async def upload_images(
        self,
        session_id: UUID4,
        file_name: str,
        images: list[Image.Image],
        start: int = 1,
    ):
        start_time = time.perf_counter()
        logger.info(
            "Uploading images | session_id={} | file={} | count={} | start_page={}",
            session_id,
            file_name,
            len(images),
            start,
        )
        tasks = [
            self._upload_image(
                session_id=session_id,
                file_name=file_name,
                page=page,
                image=image,
            )
            for page, image in zip(range(start, start + len(images)), images)
        ]
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start_time
        logger.success(
            "Images uploaded | session_id={} | count={} | time_ms={:.2f}",
            session_id,
            len(images),
            elapsed * 1000,
        )
