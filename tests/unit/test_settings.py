from __future__ import annotations

import pytest
from pydantic import ValidationError

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


def test_persistence_rejects_non_postgresql_urls() -> None:
    with pytest.raises(ValueError, match="requires PostgreSQL"):
        sqlalchemy_url("sqlite:///local.db")
