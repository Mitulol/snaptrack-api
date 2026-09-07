"""Application settings, loaded from the environment.

Every value has a development-friendly default so the test suite and a bare
``uvicorn app.main:app`` both work without a ``.env`` file. The docker-compose
stack overrides the hostnames (``postgres``, ``redis``) via environment.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    # --- Storage -----------------------------------------------------------
    database_url: str = "postgresql+psycopg2://snaptrack:snaptrack@localhost:5432/snaptrack"
    redis_url: str = "redis://localhost:6379/0"
    photo_storage_dir: str = "./_storage"

    # --- Celery ----------------------------------------------------------------
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Auth ----------------------------------------------------------------
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # --- Behaviour tuning --------------------------------------------------
    photo_cache_ttl_seconds: int = 60
    thumbnail_max_edge: int = 256
    thumbnail_task_max_retries: int = 3

    @property
    def is_testing(self) -> bool:
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
