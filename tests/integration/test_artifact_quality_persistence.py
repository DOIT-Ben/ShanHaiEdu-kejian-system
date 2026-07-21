from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from apps.api.database import build_engine, build_session_factory
from tests.integration.test_node_execution_runtime import _seed_runtime

REPORT_ID = UUID("10000000-0000-4000-8000-000000000133")


def test_quality_report_rows_reject_update_and_delete_with_stable_sqlstate(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    seeded = _seed_runtime(build_session_factory(engine))

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO artifact_quality_reports (
                    id,
                    organization_id,
                    project_id,
                    lesson_unit_id,
                    source_artifact_version_id,
                    source_content_hash,
                    content_release_id,
                    workflow_definition_version_id,
                    validate_node_run_id,
                    validator_set_json,
                    validator_set_hash,
                    conclusion,
                    findings_json,
                    evidence_hash,
                    created_at,
                    created_by
                )
                SELECT
                    :report_id,
                    artifact_versions.organization_id,
                    workflow_runs.project_id,
                    NULL,
                    artifact_versions.id,
                    artifact_versions.content_hash,
                    workflow_runs.content_release_id,
                    workflow_runs.workflow_definition_version_id,
                    node_runs.id,
                    CAST(:validator_set AS jsonb),
                    :validator_set_hash,
                    'passed',
                    CAST('[]' AS jsonb),
                    :evidence_hash,
                    now(),
                    :created_by
                FROM artifact_versions
                JOIN node_runs ON node_runs.id = :node_run_id
                JOIN workflow_runs ON workflow_runs.id = node_runs.workflow_run_id
                WHERE artifact_versions.id = :source_version_id
                """
            ),
            {
                "report_id": REPORT_ID,
                "validator_set": (
                    '[{"implementation_digest":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
                    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","key":"validator.fixture",'
                    '"semantic_version":"1.0.0"}]'
                ),
                "validator_set_hash": "b" * 64,
                "evidence_hash": "c" * 64,
                "created_by": seeded.actor.principal_id,
                "node_run_id": seeded.node_run_id,
                "source_version_id": seeded.upstream_version_id,
            },
        )

    for statement in (
        "UPDATE artifact_quality_reports SET conclusion = 'failed' WHERE id = :report_id",
        "DELETE FROM artifact_quality_reports WHERE id = :report_id",
    ):
        with pytest.raises(DBAPIError) as captured:
            with engine.begin() as connection:
                connection.execute(text(statement), {"report_id": REPORT_ID})
        assert getattr(captured.value.orig, "sqlstate", None) == "23514"
