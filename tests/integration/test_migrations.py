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
    "material_parse_versions",
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

    assert ScriptDirectory.from_config(config).get_current_head() == "f4c8d2e6a103"
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


def test_stage0_file_assets_survive_asset_extension_migration(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "e8f4a2b7c901")
    engine = create_engine(sqlalchemy_url(postgres_database_url))
    organization_id = UUID("01900000-0000-7000-8000-000000000001")
    principal_id = UUID("01900000-0000-7000-8000-000000000002")
    project_id = UUID("01960000-0000-7000-8000-000000000001")
    material_id = UUID("01960000-0000-7000-8000-000000000002")
    asset_id = UUID("01960000-0000-7000-8000-000000000003")
    version_id = UUID("01960000-0000-7000-8000-000000000004")
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
                    :id, :organization_id, 'PRJ-ASSET-MIGRATION', 'Asset migration',
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
        connection.execute(
            text(
                """
                INSERT INTO file_assets (
                    id, organization_id, asset_key, asset_kind, current_version_id,
                    status, retention_class, created_at, updated_at, created_by,
                    updated_by, lock_version
                ) VALUES (
                    :id, :organization_id, 'material:migration', 'source_material', NULL,
                    'active', 'project_source', now(), now(), :principal_id,
                    :principal_id, 1
                )
                """
            ),
            {
                "id": asset_id,
                "organization_id": organization_id,
                "principal_id": principal_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO file_asset_versions (
                    id, organization_id, file_asset_id, version_no, storage_bucket,
                    storage_key, mime_type, byte_size, sha256, etag, scan_status,
                    metadata_json, created_at, created_by
                ) VALUES (
                    :id, :organization_id, :asset_id, 1, 'shanhaiedu',
                    'immutable/migration/source.pdf', 'application/pdf', 4,
                    :sha256, 'etag-migration', 'pending', '{}'::jsonb, now(), :principal_id
                )
                """
            ),
            {
                "id": version_id,
                "organization_id": organization_id,
                "asset_id": asset_id,
                "sha256": "a" * 64,
                "principal_id": principal_id,
            },
        )
        connection.execute(
            text("UPDATE file_assets SET current_version_id = :version_id WHERE id = :asset_id"),
            {"version_id": version_id, "asset_id": asset_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO source_materials (
                    id, organization_id, project_id, material_kind, file_asset_id,
                    original_filename, mime_type, upload_status, confirmed_at,
                    confirmed_by, created_at, updated_at, created_by, updated_by,
                    lock_version
                ) VALUES (
                    :id, :organization_id, :project_id, 'textbook', :asset_id,
                    'lesson.pdf', 'application/pdf', 'confirmed', now(), :principal_id,
                    now(), now(), :principal_id, :principal_id, 1
                )
                """
            ),
            {
                "id": material_id,
                "organization_id": organization_id,
                "project_id": project_id,
                "asset_id": asset_id,
                "principal_id": principal_id,
            },
        )

    run_migration(postgres_database_url, "head")
    with engine.connect() as connection:
        version = connection.execute(
            text(
                "SELECT width, height, duration_ms, page_count, derived_from_version_id "
                "FROM file_asset_versions WHERE id = :id"
            ),
            {"id": version_id},
        ).one()
        assert version == (None, None, None, None, None)
        assert (
            connection.scalar(
                text("SELECT file_asset_id FROM source_materials WHERE id = :id"),
                {"id": material_id},
            )
            == asset_id
        )
        assert connection.scalar(text("SELECT count(*) FROM material_parse_versions")) == 0
