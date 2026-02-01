from slowapi import Limiter
from slowapi.util import get_remote_address

from app.settings import get_settings

limiter = Limiter(key_func=get_remote_address)


def get_query_rate_limit() -> str:
    """Get the query rate limit from settings."""
    return get_settings().rate_limit.query_rate_limit


def get_ingest_rate_limit() -> str:
    """Get the ingest rate limit from settings."""
    return get_settings().rate_limit.ingest_rate_limit
