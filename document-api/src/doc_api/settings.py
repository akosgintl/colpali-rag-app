from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    collection_name: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    vector_dim: int = 128  # 128 for ColQwen2.5, 320 for ColQwen3


class VLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    vlm_service_url: str = "http://localhost:8001"
    vlm_timeout_seconds: int = 120


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
    vlm: VLMSettings = VLMSettings()
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
