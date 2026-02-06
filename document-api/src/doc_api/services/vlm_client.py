import time
from io import BytesIO

import httpx
from loguru import logger
from PIL import Image
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class VLMClientError(Exception):
    """Base exception for VLM client errors."""

    pass


class VLMServiceUnavailable(VLMClientError):
    """Raised when VLM service is unavailable."""

    pass


class VLMInferenceError(VLMClientError):
    """Raised when VLM inference fails."""

    pass


class VLMClient:
    """HTTP client for communicating with the VLM embedding service."""

    def __init__(self, base_url: str, timeout_seconds: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(float(timeout_seconds)),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        logger.info(
            "VLMClient initialized | base_url={} | timeout={}s",
            self.base_url,
            timeout_seconds,
        )

    def _get_headers(self, auth_token: str | None = None) -> dict[str, str]:
        """Build headers for VLM service requests."""
        headers: dict[str, str] = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        return headers

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.info("VLMClient closed")

    async def health_check(self) -> bool:
        """Check if VLM service is healthy."""
        try:
            response = await self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning("VLM health check failed | error={}", str(e))
            return False

    @staticmethod
    def _image_to_bytes(image: Image.Image) -> tuple[str, bytes, str]:
        """Convert PIL Image to bytes for multipart upload."""
        buffer = BytesIO()
        # Ensure RGB mode for JPEG
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(buffer, format="JPEG", quality=95)
        buffer.seek(0)
        return ("images", buffer.getvalue(), "image/jpeg")

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def embed_images(
        self, images: list[Image.Image], auth_token: str | None = None
    ) -> list[list[list[float]]]:
        """
        Generate embeddings for a list of images.

        Args:
            images: List of PIL Images
            auth_token: Optional JWT token to forward to VLM service

        Returns:
            List of embeddings, each being a list of 128-dim vectors (multi-vector)
        """
        start_time = time.perf_counter()
        logger.info("Sending images to VLM service | count={}", len(images))

        # Prepare multipart files
        files = []
        for idx, img in enumerate(images):
            buffer = BytesIO()
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buffer, format="JPEG", quality=95)
            buffer.seek(0)
            files.append(("images", (f"image_{idx}.jpeg", buffer, "image/jpeg")))

        try:
            response = await self._client.post(
                f"{self.base_url}/embed/images",
                files=files,
                headers=self._get_headers(auth_token),
            )
            response.raise_for_status()
        except httpx.ConnectError as e:
            logger.error("VLM service connection failed | error={}", str(e))
            raise VLMServiceUnavailable(
                f"Cannot connect to VLM service at {self.base_url}"
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error(
                "VLM service returned error | status={} | error={}",
                e.response.status_code,
                str(e),
            )
            if e.response.status_code == 504:
                raise VLMInferenceError("VLM inference timed out") from e
            raise VLMInferenceError(
                f"VLM service error: {e.response.status_code}"
            ) from e

        data = response.json()
        elapsed = time.perf_counter() - start_time
        logger.info(
            "Embeddings received from VLM | count={} | vlm_time_ms={:.2f} | total_time_ms={:.2f}",
            len(data["embeddings"]),
            data.get("processing_time_ms", 0),
            elapsed * 1000,
        )

        return data["embeddings"]

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def embed_query(
        self, query: str, auth_token: str | None = None
    ) -> list[list[float]]:
        """
        Generate embedding for a text query.

        Args:
            query: Query string
            auth_token: Optional JWT token to forward to VLM service

        Returns:
            Multi-vector embedding (list of 128-dim vectors)
        """
        start_time = time.perf_counter()
        logger.info(
            "Sending query to VLM service | query_length={}", len(query)
        )

        try:
            response = await self._client.post(
                f"{self.base_url}/embed/query",
                json={"query": query},
                headers=self._get_headers(auth_token),
            )
            response.raise_for_status()
        except httpx.ConnectError as e:
            logger.error("VLM service connection failed | error={}", str(e))
            raise VLMServiceUnavailable(
                f"Cannot connect to VLM service at {self.base_url}"
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error(
                "VLM service returned error | status={} | error={}",
                e.response.status_code,
                str(e),
            )
            if e.response.status_code == 504:
                raise VLMInferenceError("VLM query embedding timed out") from e
            raise VLMInferenceError(
                f"VLM service error: {e.response.status_code}"
            ) from e

        data = response.json()
        elapsed = time.perf_counter() - start_time
        logger.info(
            "Query embedding received from VLM | vlm_time_ms={:.2f} | total_time_ms={:.2f}",
            data.get("processing_time_ms", 0),
            elapsed * 1000,
        )

        return data["embedding"]
