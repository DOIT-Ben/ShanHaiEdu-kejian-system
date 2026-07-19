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
    "approvals",
    "asset_bindings",
    "artifact_drafts",
    "artifact_relations",
    "artifact_versions",
    "artifacts",
    "branch_runs",
    "creation_batches",
    "creation_items",
    "creation_package_items",
    "creation_packages",
    "creation_prompt_versions",
    "content_definition_versions",
    "content_package_versions",
    "content_package_item_versions",
    "content_packages",
    "content_release_items",
    "content_releases",
    "context_snapshots",
    "file_asset_versions",
    "file_assets",
    "generation_jobs",
    "generation_results",
    "generation_attempts",
    "idempotency_records",
    "lesson_branch_configs",
    "lesson_units",
    "material_parse_versions",
    "node_input_snapshots",
    "node_runs",
    "organization_members",
    "organizations",
    "outbox_events",
    "principals",
    "projects",
    "prompt_snapshots",
    "project_members",
    "project_asset_slots",
    "project_automation_policies",
    "event_stream_entries",
    "source_materials",
    "save_to_project_operations",
    "runtime_default_versions",
    "upload_sessions",
    "usage_records",
    "users",
    "workflow_definition_versions",
    "workflow_definitions",
    "workflow_runs",
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

    database_inspector = inspect(engine)
    parse_columns = {
        column["name"] for column in database_inspector.get_columns("material_parse_versions")
    }
    parse_indexes = {
        index["name"] for index in database_inspector.get_indexes("material_parse_versions")
    }
    parse_foreign_keys = {
        foreign_key["name"]
        for foreign_key in database_inspector.get_foreign_keys("material_parse_versions")
    }
    assert "generation_job_id" in parse_columns
    assert "uq_material_parse_versions_generation_job" in parse_indexes
    assert "fk_material_parse_versions_generation_job" in parse_foreign_keys
    artifact_foreign_keys = {
        foreign_key["name"]
        for foreign_key in database_inspector.get_foreign_keys("artifact_versions")
    }
    assert "fk_artifact_versions_context_snapshot" in artifact_foreign_keys
    assert "fk_artifact_versions_prompt_snapshot" in artifact_foreign_keys
    binding_indexes = {index["name"] for index in database_inspector.get_indexes("asset_bindings")}
    assert "uq_asset_bindings_active_slot_position" in binding_indexes
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE tgname IN ("
                    "'trg_project_asset_slot_scope', "
                    "'trg_asset_binding_scope', "
                    "'trg_asset_binding_history'"
                    ") AND NOT tgisinternal"
                )
            )
            == 3
        )
    creation_batch_columns = {
        column["name"] for column in database_inspector.get_columns("creation_batches")
    }
    creation_batch_indexes = {
        index["name"] for index in database_inspector.get_indexes("creation_batches")
    }
    creation_batch_foreign_keys = {
        foreign_key["name"]
        for foreign_key in database_inspector.get_foreign_keys("creation_batches")
    }
    assert "owner_user_id" in creation_batch_columns
    assert "ix_creation_batches_organization_owner_created" in creation_batch_indexes
    assert "fk_creation_batches_owner_user_id_users" in creation_batch_foreign_keys
    generation_attempt_columns = {
        column["name"] for column in database_inspector.get_columns("generation_attempts")
    }
    generation_attempt_indexes = {
        index["name"] for index in database_inspector.get_indexes("generation_attempts")
    }
    assert "provider_task_id" in generation_attempt_columns
    assert "ix_generation_attempts_provider_task" in generation_attempt_indexes
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE tgname = 'trg_creation_batch_owner_scope' AND NOT tgisinternal"
                )
            )
            == 1
        )
    assert ScriptDirectory.from_config(config).get_current_head() == "c2d4e6f8a901"
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
        pinned_versions = connection.execute(
            text(
                "SELECT content_release_id, workflow_definition_version_id "
                "FROM projects WHERE id = :id"
            ),
            {"id": project_id},
        ).one()
        assert pinned_versions == (
            UUID("01970000-0000-7000-8000-000000000003"),
            UUID("01970000-0000-7000-8000-000000000006"),
        )
        policy = connection.execute(
            text(
                "SELECT mode, policy_version, workflow_definition_version_id "
                "FROM project_automation_policies WHERE project_id = :id"
            ),
            {"id": project_id},
        ).one()
        assert policy == (
            "guided",
            1,
            UUID("01970000-0000-7000-8000-000000000006"),
        )
        principal = connection.execute(
            text("SELECT principal_type, user_id FROM principals WHERE id = :id"),
            {"id": principal_id},
        ).one()
        assert principal == ("system", None)


def test_creation_batch_owner_is_backfilled_from_its_creator(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "d2e5f8a1c604")
    engine = create_engine(sqlalchemy_url(postgres_database_url))
    organization_id = UUID("01900000-0000-7000-8000-000000000001")
    user_id = UUID("01930000-0000-7000-8000-000000000001")
    member_id = UUID("01930000-0000-7000-8000-000000000002")
    principal_id = UUID("01930000-0000-7000-8000-000000000003")
    batch_id = UUID("01930000-0000-7000-8000-000000000004")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (id, email, display_name, status, created_at)
                VALUES (:id, 'migration-owner@example.test', 'Migration Owner', 'active', now())
                """
            ),
            {"id": user_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO organization_members (
                    id, organization_id, user_id, role, status, created_at
                ) VALUES (:id, :organization_id, :user_id, 'member', 'active', now())
                """
            ),
            {"id": member_id, "organization_id": organization_id, "user_id": user_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO principals (
                    id, organization_id, user_id, principal_type, display_name,
                    status, created_at
                ) VALUES (
                    :id, :organization_id, :user_id, 'user', 'Migration Owner',
                    'active', now()
                )
                """
            ),
            {"id": principal_id, "organization_id": organization_id, "user_id": user_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO creation_batches (
                    id, organization_id, source_kind, creation_package_id,
                    source_project_id, source_workflow_run_id, source_node_run_id,
                    studio_type, title, status, created_at, updated_at, created_by,
                    updated_by, lock_version, deleted_at
                ) VALUES (
                    :id, :organization_id, 'standalone', NULL, NULL, NULL, NULL,
                    'image', 'Migration batch', 'draft', now(), now(), :principal_id,
                    :principal_id, 1, NULL
                )
                """
            ),
            {
                "id": batch_id,
                "organization_id": organization_id,
                "principal_id": principal_id,
            },
        )

    run_migration(postgres_database_url, "head")
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT owner_user_id FROM creation_batches WHERE id = :id"),
                {"id": batch_id},
            )
            == user_id
        )


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
