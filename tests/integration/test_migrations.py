from __future__ import annotations

import os
from uuid import UUID

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from apps.api.database import build_session_factory, sqlalchemy_url, utc_now
from apps.api.ids import new_uuid7
from apps.api.model_gateway.attempt_recovery import AttemptRecoveryCoordinator
from apps.api.model_gateway.audit_models import (
    GenerationAttempt,
    GenerationAttemptCounter,
    UsageRecord,
)
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.workflows.service import WorkflowRuntimeService
from tests.conftest import run_migration
from tests.fakes.identity import seed_test_actor
from workflow.node_state import NodeStatus

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
    "generation_attempt_counters",
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
    assert {
        "provider_task_id",
        "operation_kind",
        "lease_owner",
        "lease_expires_at",
        "heartbeat_at",
        "cancel_requested_at",
    }.issubset(generation_attempt_columns)
    assert "ix_generation_attempts_provider_task" in generation_attempt_indexes
    assert "ix_generation_attempts_status_lease" in generation_attempt_indexes
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
    package_columns = {
        column["name"] for column in database_inspector.get_columns("creation_packages")
    }
    package_indexes = {
        index["name"] for index in database_inspector.get_indexes("creation_packages")
    }
    package_foreign_keys = {
        foreign_key["name"]
        for foreign_key in database_inspector.get_foreign_keys("creation_packages")
    }
    assert {"source_artifact_version_id", "lesson_unit_id"}.issubset(package_columns)
    assert "ix_creation_packages_source_artifact_version" in package_indexes
    assert {
        "fk_creation_packages_source_artifact_version",
        "fk_creation_packages_lesson_unit",
    }.issubset(package_foreign_keys)
    package_item_columns = {
        column["name"] for column in database_inspector.get_columns("creation_package_items")
    }
    assert "reference_assets_json" in package_item_columns
    node_run_columns = {
        column["name"] for column in database_inspector.get_columns("node_runs")
    }
    assert {
        "execution_owner_token",
        "execution_lease_expires_at",
    }.issubset(node_run_columns)
    assert ScriptDirectory.from_config(config).get_current_head() == "g1b2c3d4e5f6"
    previous = os.environ.get("SHANHAI_DATABASE_URL")
    os.environ["SHANHAI_DATABASE_URL"] = postgres_database_url
    try:
        command.check(config)
    finally:
        if previous is None:
            os.environ.pop("SHANHAI_DATABASE_URL", None)
        else:
            os.environ["SHANHAI_DATABASE_URL"] = previous


def test_running_attempt_is_backfilled_and_recovered_after_lease_migration(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "c2d4e6f8a901")
    engine = create_engine(sqlalchemy_url(postgres_database_url))
    factory = build_session_factory(engine)
    attempt_id = new_uuid7()
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Lease migration", knowledge_point="One half")
        )
        run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
        node = WorkflowRuntimeService(session, actor).create_project_node_run(
            run.id,
            node_key="prepare",
            status=NodeStatus.READY,
        )
        session.execute(
            text(
                """
                INSERT INTO generation_attempts (
                    id, organization_id, project_id, node_run_id, generation_job_id,
                    attempt_no, request_id, capability, provider_name, provider_model,
                    route_reason, status, request_hash, provider_request_id,
                    provider_task_id, submitted_at, finished_at, error_code,
                    error_details_json, latency_ms
                ) VALUES (
                    :id, :organization_id, :project_id, :node_run_id, NULL,
                    1, 'req-legacy-running', 'video.image_to_video.6s_30s',
                    'provider-test', 'model-test', 'configured_primary', 'running',
                    :request_hash, NULL, NULL, now() - interval '10 minutes',
                    NULL, NULL, '{}'::jsonb, NULL
                )
                """
            ),
            {
                "id": attempt_id,
                "organization_id": actor.organization_id,
                "project_id": project.id,
                "node_run_id": node.id,
                "request_hash": "a" * 64,
            },
        )

    run_migration(postgres_database_url, "head")
    with factory() as session:
        attempt = session.get(GenerationAttempt, attempt_id)
        counter = session.get(GenerationAttemptCounter, node.id)
    assert attempt is not None
    assert attempt.operation_kind == "legacy_unknown"
    assert attempt.heartbeat_at is not None
    assert attempt.lease_expires_at is not None
    assert attempt.heartbeat_at < attempt.lease_expires_at < utc_now()
    assert counter is not None and counter.next_attempt_no == 2

    result = AttemptRecoveryCoordinator(factory).reconcile()

    with factory() as session:
        attempt = session.get(GenerationAttempt, attempt_id)
        usage = session.scalar(
            select(UsageRecord).where(UsageRecord.generation_attempt_id == attempt_id)
        )
    assert result.submission_unknown == 1
    assert attempt is not None and attempt.status == "submission_unknown"
    assert usage is not None and usage.actual_cost is None

    previous = os.environ.get("SHANHAI_DATABASE_URL")
    os.environ["SHANHAI_DATABASE_URL"] = postgres_database_url
    try:
        command.downgrade(Config("alembic.ini"), "c2d4e6f8a901")
    finally:
        if previous is None:
            os.environ.pop("SHANHAI_DATABASE_URL", None)
        else:
            os.environ["SHANHAI_DATABASE_URL"] = previous
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM generation_attempts WHERE id = :id"),
                {"id": attempt_id},
            )
            == "failed"
        )
        assert "operation_kind" not in {
            column["name"] for column in inspect(engine).get_columns("generation_attempts")
        }


def test_populated_attempt_migration_round_trip_restores_identity_trigger(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "c2d4e6f8a901")
    engine = create_engine(sqlalchemy_url(postgres_database_url))
    factory = build_session_factory(engine)
    statuses = ("running", "succeeded", "failed", "cancelled")
    attempt_ids = {status: new_uuid7() for status in statuses}
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Populated lease migration", knowledge_point="One half")
        )
        run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
        node = WorkflowRuntimeService(session, actor).create_project_node_run(
            run.id,
            node_key="prepare",
            status=NodeStatus.READY,
        )
        for attempt_no, status in enumerate(statuses, start=1):
            is_running = status == "running"
            error_code = None if status in {"running", "succeeded"} else f"MODEL_{status.upper()}"
            session.execute(
                text(
                    """
                    INSERT INTO generation_attempts (
                        id, organization_id, project_id, node_run_id, generation_job_id,
                        attempt_no, request_id, capability, provider_name, provider_model,
                        route_reason, status, request_hash, provider_request_id,
                        provider_task_id, submitted_at, finished_at, error_code,
                        error_details_json, latency_ms
                    ) VALUES (
                        :id, :organization_id, :project_id, :node_run_id, NULL,
                        :attempt_no, :request_id, 'text.smoke', 'provider-test', 'model-test',
                        'configured_primary', :status, :request_hash, NULL, NULL,
                        now() - interval '10 minutes',
                        CASE WHEN :is_running THEN NULL ELSE now() END,
                        :error_code, '{}'::jsonb,
                        CASE WHEN :is_running THEN NULL ELSE 10 END
                    )
                    """
                ),
                {
                    "id": attempt_ids[status],
                    "organization_id": actor.organization_id,
                    "project_id": project.id,
                    "node_run_id": node.id,
                    "attempt_no": attempt_no,
                    "request_id": f"req-populated-{status}",
                    "status": status,
                    "request_hash": f"{attempt_no:x}" * 64,
                    "is_running": is_running,
                    "error_code": error_code,
                },
            )
            if not is_running:
                session.execute(
                    text(
                        """
                        INSERT INTO usage_records (
                            id, organization_id, user_id, project_id, node_run_id,
                            generation_attempt_id, capability, provider_name, provider_model,
                            input_units_json, output_units_json, pricing_version,
                            estimated_cost, actual_cost, currency, latency_ms, created_at
                        ) VALUES (
                            :id, :organization_id, :user_id, :project_id, :node_run_id,
                            :attempt_id, 'text.smoke', 'provider-test', 'model-test',
                            '{"prompt_tokens": 1}'::jsonb,
                            '{"completion_tokens": 1, "total_tokens": 2}'::jsonb,
                            NULL, NULL, 0.010000, 'USD', 10, now()
                        )
                        """
                    ),
                    {
                        "id": new_uuid7(),
                        "organization_id": actor.organization_id,
                        "user_id": actor.user_id,
                        "project_id": project.id,
                        "node_run_id": node.id,
                        "attempt_id": attempt_ids[status],
                    },
                )

    run_migration(postgres_database_url, "head")
    with engine.connect() as connection:
        migrated = dict(
            connection.execute(
                text("SELECT id, status FROM generation_attempts WHERE node_run_id = :node_id"),
                {"node_id": node.id},
            )
            .tuples()
            .all()
        )
        assert migrated == {attempt_ids[status]: status for status in statuses}
        assert connection.scalar(text("SELECT count(*) FROM usage_records")) == 3
        assert _attempt_identity_trigger_count(connection) == 1
    _assert_attempt_identity_check_violation(engine, attempt_ids["succeeded"])

    recovered = AttemptRecoveryCoordinator(factory).reconcile()
    assert recovered.submission_unknown == 1
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM usage_records")) == 4

    previous = os.environ.get("SHANHAI_DATABASE_URL")
    os.environ["SHANHAI_DATABASE_URL"] = postgres_database_url
    try:
        command.downgrade(Config("alembic.ini"), "c2d4e6f8a901")
    finally:
        if previous is None:
            os.environ.pop("SHANHAI_DATABASE_URL", None)
        else:
            os.environ["SHANHAI_DATABASE_URL"] = previous
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM generation_attempts WHERE id = :id"),
                {"id": attempt_ids["running"]},
            )
            == "failed"
        )
        assert connection.scalar(text("SELECT count(*) FROM usage_records")) == 4
        assert _attempt_identity_trigger_count(connection) == 1
    _assert_attempt_identity_check_violation(engine, attempt_ids["succeeded"])

    run_migration(postgres_database_url, "head")
    with engine.connect() as connection:
        rows = list(
            connection.execute(
                text(
                    "SELECT status, operation_kind FROM generation_attempts "
                    "WHERE node_run_id = :node_id ORDER BY attempt_no"
                ),
                {"node_id": node.id},
            )
        )
        assert rows == [
            ("failed", "legacy_unknown"),
            ("succeeded", "legacy_unknown"),
            ("failed", "legacy_unknown"),
            ("cancelled", "legacy_unknown"),
        ]
        assert connection.scalar(text("SELECT count(*) FROM usage_records")) == 4
        assert _attempt_identity_trigger_count(connection) == 1
    _assert_attempt_identity_check_violation(engine, attempt_ids["succeeded"])


def _attempt_identity_trigger_count(connection) -> int:
    value = connection.scalar(
        text(
            "SELECT count(*) FROM pg_trigger "
            "WHERE tgname = 'trg_generation_attempt_identity' AND NOT tgisinternal"
        )
    )
    assert isinstance(value, int)
    return value


def _assert_attempt_identity_check_violation(engine, attempt_id: UUID) -> None:
    with pytest.raises(IntegrityError) as captured:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE generation_attempts SET route_reason = 'tampered' WHERE id = :id"),
                {"id": attempt_id},
            )
    assert getattr(captured.value.orig, "sqlstate", None) == "23514"


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
