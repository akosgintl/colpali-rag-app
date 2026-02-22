import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from vlm.settings import Settings, get_settings

security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not settings.auth.auth_enabled:
        return None

    if credentials is None:
        logger.warning("Authentication failed | reason=no_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not settings.auth.vlm_api_key:
        logger.error("Auth enabled but VLM_API_KEY not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication not properly configured",
        )

    if not secrets.compare_digest(
        credentials.credentials, settings.auth.vlm_api_key
    ):
        logger.warning("Authentication failed | reason=invalid_api_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("API key verified")
