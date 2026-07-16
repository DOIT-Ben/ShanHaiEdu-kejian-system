"""Environment-backed application settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with no embedded production credentials."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SHANHAI_",
        extra="ignore",
    )

    service_name: str = "shanhaiedu-api"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)

    database_url: SecretStr | None = None
    redis_url: SecretStr | None = None
    object_storage_health_url: HttpUrl | None = None
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    @model_validator(mode="after")
    def require_production_dependencies(self) -> Self:
        if self.environment != "production":
            return self
        missing = [
            name
            for name in ("database_url", "redis_url", "object_storage_health_url")
            if getattr(self, name) is None
        ]
        if missing:
            fields = ", ".join(missing)
            raise ValueError(f"production configuration is missing required fields: {fields}")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
