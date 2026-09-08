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
    # Which build is answering. The canary stack (docker-compose profile
    # "canary") runs a second API as "next"; Traefik splits traffic 90/10.
    release_channel: str = "stable"

    # --- Storage -----------------------------------------------------------
    database_url: str = "postgresql+psycopg2://snaptrack:snaptrack@localhost:5432/snaptrack"
    redis_url: str = "redis://localhost:6379/0"
    photo_storage_dir: str = "./_storage"

    # Per-worker SQLAlchemy pool. Keep (pool_size + max_overflow) * WEB_CONCURRENCY
    # comfortably under Postgres max_connections. See docs/adr/0001-load-test-tuning.md.
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # --- Celery ----------------------------------------------------------------
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Auth ----------------------------------------------------------------
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # --- Behaviour tuning --------------------------------------------------
    # 5 min: reads dominate and every write path invalidates the key explicitly,
    # so a longer TTL trades no correctness for a higher hit rate under load.
    photo_cache_ttl_seconds: int = 300
    thumbnail_max_edge: int = 256
    thumbnail_task_max_retries: int = 3

    # --- Notifications -------------------------------------------------------
    # No real SMTP in a laptop-only stack. "console" logs the message; "file"
    # drops an RFC-822 .eml into ``notification_mail_dir``.
    notification_backend: str = "console"  # console | file
    notification_mail_dir: str = "./_mail"
    notification_from_addr: str = "moderation@snaptrack.local"
    notification_task_max_retries: int = 3

    @property
    def is_testing(self) -> bool:
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
