"""Environment-backed application settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with no embedded production credentials."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SHANHAI_",
        env_ignore_empty=True,
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
    material_parse_max_pages: int = Field(default=500, ge=1, le=5_000)
    material_parse_max_text_chars: int = Field(default=5_000_000, ge=1)
    material_parse_max_text_blocks: int = Field(default=100_000, ge=1)
    material_parse_max_image_references: int = Field(default=10_000, ge=1)
    material_parse_timeout_seconds: float = Field(default=30, gt=0, le=300)
    outbox_retry_seconds: int = Field(default=5, ge=1, le=300)
    outbox_poll_seconds: float = Field(default=0.5, gt=0, le=30)
    sse_poll_seconds: float = Field(default=0.5, gt=0, le=30)
    sse_heartbeat_seconds: float = Field(default=15, gt=0, le=60)
    text_provider_name: str | None = None
    text_provider_base_url: HttpUrl | None = None
    text_provider_model: str | None = None
    text_provider_secret_env: str = Field(
        default="NEWAPI_TEXT_API_KEY",
        pattern=r"^[A-Z][A-Z0-9_]{2,127}$",
    )
    text_provider_timeout_seconds: float = Field(default=30, gt=0, le=120)
    video_provider_name: str | None = None
    video_provider_base_url: HttpUrl | None = None
    video_provider_model: str | None = None
    video_provider_secret_env: str = Field(
        default="MODEL_GATEWAY_API_KEY",
        pattern=r"^[A-Z][A-Z0-9_]{2,127}$",
    )
    video_provider_timeout_seconds: float = Field(default=120, gt=0, le=600)
    video_provider_poll_seconds: float = Field(default=2, gt=0, le=60)
    video_provider_max_wait_seconds: int = Field(default=300, ge=10, le=900)
    video_provider_max_download_bytes: int = Field(
        default=104_857_600,
        ge=1,
        le=1_073_741_824,
    )
    provider_media_root: Path | None = None
    provider_media_public_base_url: HttpUrl | None = None
    provider_media_signing_secret_env: str = Field(
        default="SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET",
        pattern=r"^[A-Z][A-Z0-9_]{2,127}$",
    )
    provider_media_max_ttl_seconds: int = Field(default=300, ge=1, le=3600)
    provider_media_max_file_bytes: int = Field(default=10_485_760, ge=1)

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
