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
    object_storage_endpoint: str | None = None
    object_storage_access_key: SecretStr | None = None
    object_storage_secret_key: SecretStr | None = None
    object_storage_secure: bool = True
    object_storage_bucket: str = Field(default="shanhaiedu", min_length=3, max_length=63)
    upload_session_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    max_upload_size_bytes: int = Field(default=52_428_800, ge=1)
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    idempotency_ttl_seconds: int = Field(default=86_400, ge=60, le=604_800)
    worker_lease_seconds: int = Field(default=60, ge=5, le=3600)
    outbox_retry_seconds: int = Field(default=5, ge=1, le=300)
    outbox_poll_seconds: float = Field(default=0.5, gt=0, le=30)
    sse_poll_seconds: float = Field(default=0.5, gt=0, le=30)
    sse_heartbeat_seconds: float = Field(default=15, gt=0, le=60)

    @model_validator(mode="after")
    def require_production_dependencies(self) -> Self:
        if self.environment != "production":
            return self
        missing = [
            name
            for name in (
                "database_url",
                "redis_url",
                "object_storage_health_url",
                "object_storage_endpoint",
                "object_storage_access_key",
                "object_storage_secret_key",
            )
            if getattr(self, name) is None
        ]
        if missing:
            fields = ", ".join(missing)
            raise ValueError(f"production configuration is missing required fields: {fields}")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
