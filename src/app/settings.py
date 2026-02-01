from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    collection_name: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""


class ColpaliSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    colpali_model_name: str = "vidore/colqwen2.5-v0.2"
    max_concurrent_inferences: int = 1


class SupabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_key: str = ""
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    bucket: str = "colpali"


class AnthropicSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192
    temperature: float = 0.0


class ProcessingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    max_file_size_mb: int = 50
    max_total_upload_mb: int = 200
    max_pages_per_batch: int = 5
    max_pdf_pages: int = 200
    clear_cuda_cache_interval: int = 10


class TimeoutSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Overall request timeouts
    ingest_endpoint_timeout_seconds: int = 600
    query_endpoint_timeout_seconds: int = 180

    # Integration-specific timeouts
    qdrant_timeout_seconds: int = 60
    supabase_timeout_seconds: int = 120
    anthropic_timeout_seconds: int = 180

    # Processing timeouts
    pdf_conversion_timeout_seconds: int = 120
    colpali_inference_timeout_seconds: int = 60


class RateLimitSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    query_rate_limit: str = "30/minute"
    ingest_rate_limit: str = "10/minute"


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth_enabled: bool = True
    allowed_origins: list[str] = ["*"]


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    workers: int = 1
    host: str = "0.0.0.0"
    port: int = 8000


class Settings(BaseSettings):
    qdrant: QdrantSettings = QdrantSettings()
    colpali: ColpaliSettings = ColpaliSettings()
    supabase: SupabaseSettings = SupabaseSettings()
    anthropic: AnthropicSettings = AnthropicSettings()
    processing: ProcessingSettings = ProcessingSettings()
    timeout: TimeoutSettings = TimeoutSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    auth: AuthSettings = AuthSettings()
    server: ServerSettings = ServerSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
