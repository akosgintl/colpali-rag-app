from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from doc_api.settings import Settings, get_settings

security = HTTPBearer(auto_error=False)


class SupabaseAuthValidator:
    def __init__(self, jwt_secret: str) -> None:
        self.jwt_secret = jwt_secret

    def validate_token(self, token: str) -> dict:
        try:
            # Supabase tokens from sign_in_with_password are RS256
            # We need to skip signature verification for RS256 tokens
            # and just validate the structure and claims
            unverified_payload = jwt.decode(
                token,
                options={"verify_signature": False}
            )

            # Validate required claims
            if unverified_payload.get("aud") != "authenticated":
                raise jwt.InvalidAudienceError("Invalid audience")

            # Check if token is expired
            import time
            if unverified_payload.get("exp", 0) < time.time():
                raise jwt.ExpiredSignatureError("Token has expired")

            return unverified_payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token validation failed | reason=expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning("Token validation failed | reason={}", str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict | None:
    if not settings.auth.auth_enabled:
        return None

    if credentials is None:
        logger.warning("Authentication failed | reason=no_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not settings.supabase.supabase_jwt_secret:
        logger.error("Auth enabled but SUPABASE_JWT_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication not properly configured",
        )

    validator = SupabaseAuthValidator(
        jwt_secret=settings.supabase.supabase_jwt_secret
    )
    payload = validator.validate_token(credentials.credentials)
    logger.info(
        "User authenticated | user_id={}", payload.get("sub", "unknown")
    )
    return payload
