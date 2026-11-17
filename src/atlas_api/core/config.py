"""Application settings (pydantic-settings). Values come from env vars or a local .env file."""
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://atlas:atlas@localhost:5432/atlas"
    cors_origins: Annotated[list[str], NoDecode] = []
    log_level: str = "INFO"
    auto_migrate: bool = True  # bring the schema to Alembic head at startup (migrate.py); AUTO_MIGRATE=false to skip
    # spec 019 item 5: a SMALL bounded pool per process + a short wait, so a burst gets fast 503s
    # instead of hanging. Total DB connections = processes x (pool_size + max_overflow): keep it under
    # the Supabase pooler limit. pool_timeout = seconds a request waits for a free connection.
    db_pool_size: int = 5
    db_max_overflow: int = 2
    db_pool_timeout: float = 3.0
    # data_version (ETag) is re-read from the DB at most every N seconds per process (0 = every request)
    data_version_ttl: float = 5.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
