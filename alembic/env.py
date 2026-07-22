"""Alembic environment bound to the explicit PostgreSQL runtime URL."""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from apps.api.artifact_quality import models as artifact_quality_models
from apps.api.artifacts import models as artifact_models
from apps.api.assets import models as asset_models
from apps.api.assets import project_models as project_asset_models
from apps.api.content_runtime import models as content_runtime_models
from apps.api.creation import models as creation_models
from apps.api.database import Base, sqlalchemy_url
from apps.api.identity import models as identity_models
from apps.api.intro_selections import models as intro_selection_models
from apps.api.jobs import models as job_models
from apps.api.lessons import models as lesson_models
from apps.api.model_gateway import audit_models as model_gateway_audit_models
from apps.api.node_execution import models as node_execution_models
from apps.api.projects import models as project_models
from apps.api.prompt_runtime import models as prompt_runtime_models
from apps.api.reliability import models as reliability_models
from apps.api.uploads import models as upload_models
from apps.api.workflows import models as workflow_models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_registered_models = (
    artifact_models,
    artifact_quality_models,
    asset_models,
    project_asset_models,
    content_runtime_models,
    creation_models,
    identity_models,
    intro_selection_models,
    job_models,
    lesson_models,
    model_gateway_audit_models,
    node_execution_models,
    project_models,
    prompt_runtime_models,
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
