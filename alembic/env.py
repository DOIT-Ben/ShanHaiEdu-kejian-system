"""Alembic environment bound to the explicit PostgreSQL runtime URL."""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from apps.api.assets import models as asset_models
from apps.api.content_runtime import models as content_runtime_models
from apps.api.database import Base, sqlalchemy_url
from apps.api.identity import models as identity_models
from apps.api.jobs import models as job_models
from apps.api.lessons import models as lesson_models
from apps.api.projects import models as project_models
from apps.api.reliability import models as reliability_models
from apps.api.uploads import models as upload_models
from apps.api.workflows import models as workflow_models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_registered_models = (
    asset_models,
    content_runtime_models,
    identity_models,
    job_models,
    lesson_models,
    project_models,
    reliability_models,
    upload_models,
    workflow_models,
)
target_metadata = Base.metadata


def configured_url() -> str:
    database_url = os.environ.get("SHANHAI_DATABASE_URL")
    if not database_url:
        raise RuntimeError("SHANHAI_DATABASE_URL is required for Alembic")
    return sqlalchemy_url(database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=configured_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = configured_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
