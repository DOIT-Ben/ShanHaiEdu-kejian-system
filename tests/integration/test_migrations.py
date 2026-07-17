from __future__ import annotations

import os
from uuid import UUID

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from alembic import command
from apps.api.database import sqlalchemy_url
from tests.conftest import run_migration

EXPECTED_TABLES = {
    "alembic_version",
    "file_asset_versions",
    "file_assets",
    "generation_jobs",
    "idempotency_records",
    "lesson_branch_configs",
    "lesson_units",
    "organization_members",
    "organizations",
    "outbox_events",
    "principals",
    "projects",
    "project_members",
    "event_stream_entries",
    "source_materials",
    "upload_sessions",
    "users",
}


def test_empty_database_upgrade_downgrade_upgrade(postgres_database_url: str) -> None:
    config = Config("alembic.ini")
    run_migration(postgres_database_url, "head")
    engine = create_engine(sqlalchemy_url(postgres_database_url))
    assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))

    run_migration(postgres_database_url, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}

    run_migration(postgres_database_url, "head")
    assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))

    assert ScriptDirectory.from_config(config).get_current_head() == "e8f4a2b7c901"
    previous = os.environ.get("SHANHAI_DATABASE_URL")
    os.environ["SHANHAI_DATABASE_URL"] = postgres_database_url
    try:
        command.check(config)
    finally:
        if previous is None:
            os.environ.pop("SHANHAI_DATABASE_URL", None)
        else:
            os.environ["SHANHAI_DATABASE_URL"] = previous


def test_stage0_project_data_survives_identity_migration(postgres_database_url: str) -> None:
    run_migration(postgres_database_url, "c6b7d8e9f001")
    engine = create_engine(sqlalchemy_url(postgres_database_url))
    project_id = UUID("01920000-0000-7000-8000-000000000001")
    organization_id = UUID("01900000-0000-7000-8000-000000000001")
    principal_id = UUID("01900000-0000-7000-8000-000000000002")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO projects (
                    id, organization_id, project_no, title, subject, school_stage,
                    knowledge_point, default_language, status, automation_mode,
                    owner_principal_id, created_at, updated_at, created_by, updated_by,
                    lock_version
                ) VALUES (
                    :id, :organization_id, 'PRJ-STAGE0', 'Stage zero project',
                    'primary_math', 'primary', 'One half', 'zh-CN', 'draft', 'assisted',
                    :principal_id, now(), now(), :principal_id, :principal_id, 1
                )
                """
            ),
            {
                "id": project_id,
                "organization_id": organization_id,
                "principal_id": principal_id,
            },
        )

    run_migration(postgres_database_url, "head")
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM projects WHERE id = :id"),
                {"id": project_id},
            )
            == 1
        )
        assert connection.scalar(text("SELECT count(*) FROM project_members")) == 0
        principal = connection.execute(
            text("SELECT principal_type, user_id FROM principals WHERE id = :id"),
            {"id": principal_id},
        ).one()
        assert principal == ("system", None)
