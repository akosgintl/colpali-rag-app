import asyncio

from fastapi import Request, Response, status
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from doc_api.settings import get_settings


class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        endpoint_timeouts: dict[str, int] | None = None,
    ) -> None:
        super().__init__(app)
        self.endpoint_timeouts = endpoint_timeouts or {}
        self.settings = get_settings()

    async def dispatch(self, request: Request, call_next) -> Response:
        # Determine timeout based on endpoint path
        path = request.url.path
        
        # Skip timeout for health checks and FastAPI built-in endpoints
        if path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)
        
        if path == "/ingest-pdfs/":
            timeout = self.settings.timeout.ingest_endpoint_timeout_seconds
        elif path == "/query/":
            timeout = self.settings.timeout.query_endpoint_timeout_seconds
        else:
            # Default timeout for other endpoints
            timeout = self.settings.timeout.query_endpoint_timeout_seconds

        logger.info(f"TimeoutMiddleware: path={path} | timeout={timeout}")

        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "Request timeout | path={} | timeout_seconds={}",
                path,
                timeout,
            )
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={"detail": f"Request timed out after {timeout} seconds"},
            )
