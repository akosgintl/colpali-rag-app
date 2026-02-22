from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ColpaliSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    colpali_model_name: str = "vidore/colqwen2.5-v0.2"
    colpali_model_type: str = "auto"  # "colqwen2.5" | "colqwen3" | "tomoro-colqwen3" | "auto"
    colpali_vector_dim: int = 128  # 128 for ColQwen2.5, 320 for ColQwen3/TomoroAI
    max_concurrent_inferences: int = 1


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    workers: int = 1
    host: str = "0.0.0.0"
    port: int = 8000


class TimeoutSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    inference_timeout_seconds: int = 60


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth_enabled: bool = False
    vlm_api_key: str = ""


class Settings(BaseSettings):
    colpali: ColpaliSettings = ColpaliSettings()
    server: ServerSettings = ServerSettings()
    timeout: TimeoutSettings = TimeoutSettings()
    auth: AuthSettings = AuthSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
