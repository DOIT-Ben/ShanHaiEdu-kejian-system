from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from apps.api.database import sqlalchemy_url
from apps.api.settings import Settings


def test_settings_use_shanhai_environment_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHANHAI_ENVIRONMENT", "test")
    monkeypatch.setenv("SHANHAI_API_PORT", "8123")
    monkeypatch.setenv("SHANHAI_DATABASE_URL", "postgresql://user:password@db/test")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.api_port == 8123
    assert settings.database_url is not None
    assert settings.database_url.get_secret_value().endswith("@db/test")
    assert "password" not in repr(settings.database_url)


def test_development_can_boot_without_dependency_configuration() -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url=None,
        redis_url=None,
        object_storage_health_url=None,
    )

    assert settings.database_url is None
    assert settings.redis_url is None
    assert settings.object_storage_health_url is None


def test_env_example_is_a_loadable_local_quick_start_configuration() -> None:
    settings = Settings(_env_file=Path(".env.example"))

    assert settings.environment == "development"
    assert settings.text_provider_name is None
    assert settings.text_provider_base_url is None
    assert settings.text_provider_model is None
    assert settings.text_provider_secret_env == "NEWAPI_TEXT_API_KEY"
    assert settings.video_provider_name is None
    assert settings.video_provider_base_url is None
    assert settings.video_provider_model is None
    assert settings.video_provider_secret_env == "MODEL_GATEWAY_API_KEY"
    assert settings.provider_media_root is None
    assert settings.provider_media_public_base_url is None
    assert settings.provider_media_signing_secret_env == "SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET"


def test_production_requires_all_dependency_configuration() -> None:
    with pytest.raises(ValidationError, match="production configuration is missing"):
        Settings(
            _env_file=None,
            environment="production",
            database_url=None,
            redis_url=None,
            object_storage_health_url=None,
        )


def test_production_requires_object_storage_credentials() -> None:
    with pytest.raises(ValidationError, match="object_storage_endpoint"):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql://database.example/shanhai",
            redis_url="redis://redis.example/0",
            object_storage_health_url="https://storage.example/health/ready",
            object_storage_endpoint=None,
            object_storage_access_key=None,
            object_storage_secret_key=None,
        )


def test_production_rejects_insecure_session_cookie_configuration() -> None:
    with pytest.raises(ValidationError, match="session cookies must remain secure"):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql://database.example/shanhai",
            redis_url="redis://redis.example/0",
            object_storage_health_url="https://storage.example/health/ready",
            object_storage_endpoint="storage.example",
            object_storage_access_key=SecretStr("test-only-access-key"),
            object_storage_secret_key=SecretStr("test-only-secret-key"),
            session_access_code=SecretStr("x" * 24),
            session_csrf_secret=SecretStr("y" * 32),
            session_teacher_principal_id=UUID("01960000-0000-7000-8000-000000000001"),
            session_allowed_origins=["https://teacher.example"],
            session_cookie_secure=False,
        )


def test_persistence_rejects_non_postgresql_urls() -> None:
    with pytest.raises(ValueError, match="requires PostgreSQL"):
        sqlalchemy_url("sqlite:///local.db")
