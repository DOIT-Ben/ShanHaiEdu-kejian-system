from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.binding import (
    resolve_quality_report_binding,
    validator_set_payload,
)
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.workflows.service import WorkflowRuntimeService
from tests.integration.test_node_execution_runtime import (
    _seed_approved_artifact,  # pyright: ignore[reportPrivateUsage]
    _seed_runtime,  # pyright: ignore[reportPrivateUsage]
)
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

REPORT_ID = UUID("10000000-0000-4000-8000-000000000133")
MISMATCH_ID = UUID("20000000-0000-4000-8000-000000000133")
ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"

_DIRECT_INSERT = text(
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
    ) VALUES (
        :report_id,
        :organization_id,
        :project_id,
        :lesson_unit_id,
        :source_artifact_version_id,
        :source_content_hash,
        :content_release_id,
        :workflow_definition_version_id,
        :validate_node_run_id,
        CAST(:validator_set AS jsonb),
        :validator_set_hash,
        'passed',
        CAST('[]' AS jsonb),
        :evidence_hash,
        now(),
        :created_by
    )
    """
)


def test_quality_report_rows_reject_update_and_delete_with_stable_sqlstate(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded, quality_node_id, source_version_id = _seed_valid_quality_node(factory)
    facts = _load_report_facts(
        engine,
        node_run_id=quality_node_id,
        source_version_id=source_version_id,
        created_by=seeded.actor.principal_id,
    )

    with engine.begin() as connection:
        connection.execute(_DIRECT_INSERT, facts)

    for statement in (
        "UPDATE artifact_quality_reports SET conclusion = 'failed' WHERE id = :report_id",
        "DELETE FROM artifact_quality_reports WHERE id = :report_id",
    ):
        with pytest.raises(DBAPIError) as captured:
            with engine.begin() as connection:
                connection.execute(text(statement), {"report_id": REPORT_ID})
        assert getattr(captured.value.orig, "sqlstate", None) == "23514"


@pytest.mark.parametrize(
    "field",
    [
        "organization_id",
        "project_id",
        "lesson_unit_id",
        "source_artifact_version_id",
        "source_content_hash",
        "content_release_id",
        "workflow_definition_version_id",
        "validate_node_run_id",
    ],
)
def test_quality_report_insert_rejects_every_mismatched_fixed_fact(
    migrated_database_url: str,
    field: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded, quality_node_id, source_version_id = _seed_valid_quality_node(factory)
    validator_set, validator_set_hash = _validator_facts()
    with factory() as session, session.begin():
        other_project = ProjectRepository(session, seeded.actor).create(
            CreateProjectRequest(title="Other scope", knowledge_point="Mismatch")
        )

    with engine.connect() as connection:
        facts = dict(
            connection.execute(
                text(
                    """
                    SELECT
                        artifact_versions.organization_id,
                        workflow_runs.project_id,
                        artifacts.lesson_unit_id,
                        artifact_versions.id AS source_artifact_version_id,
                        artifact_versions.content_hash AS source_content_hash,
                        workflow_runs.content_release_id,
                        workflow_runs.workflow_definition_version_id,
                        node_runs.id AS validate_node_run_id
                    FROM artifact_versions
                    JOIN artifacts ON artifacts.id = artifact_versions.artifact_id
                    JOIN node_runs ON node_runs.id = :node_run_id
                    JOIN workflow_runs ON workflow_runs.id = node_runs.workflow_run_id
                    WHERE artifact_versions.id = :source_version_id
                    """
                ),
                {
                    "node_run_id": quality_node_id,
                    "source_version_id": source_version_id,
                },
            )
            .mappings()
            .one()
        )
    facts.update(
        report_id=REPORT_ID,
        validator_set=validator_set,
        validator_set_hash=validator_set_hash,
        evidence_hash="c" * 64,
        created_by=seeded.actor.principal_id,
    )
    facts[field] = (
        "d" * 64
        if field == "source_content_hash"
        else other_project.id
        if field == "project_id"
        else MISMATCH_ID
    )

    with pytest.raises(DBAPIError) as captured:
        with engine.begin() as connection:
            connection.execute(_DIRECT_INSERT, facts)
    assert getattr(captured.value.orig, "sqlstate", None) == "23514"


def test_quality_report_insert_rejects_node_without_declared_source_binding(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    seeded = _seed_runtime(build_session_factory(engine))
    facts = _load_report_facts(
        engine,
        node_run_id=seeded.node_run_id,
        source_version_id=seeded.upstream_version_id,
        created_by=seeded.actor.principal_id,
    )

    with pytest.raises(DBAPIError) as captured:
        with engine.begin() as connection:
            connection.execute(_DIRECT_INSERT, facts)
    assert getattr(captured.value.orig, "sqlstate", None) == "23514"


def test_quality_report_insert_rejects_same_scope_source_not_frozen_by_validate_node(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded, quality_node_id, source_version_id = _seed_valid_quality_node(factory)
    with factory() as session, session.begin():
        source = session.get(ArtifactVersion, source_version_id)
        source_artifact = session.get(
            Artifact,
            source.artifact_id if source is not None else None,
        )
        assert source is not None and source_artifact is not None
        wrong_source = _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            source_artifact.content_definition_version_id,
            artifact_key="same-scope-wrong-quality-source",
            artifact_type="lesson_division",
            branch_key="project",
            lesson_unit_id=None,
            content=dict(source.content_json),
        )
        wrong_source_id = wrong_source.id

    facts = _load_report_facts(
        engine,
        node_run_id=quality_node_id,
        source_version_id=wrong_source_id,
        created_by=seeded.actor.principal_id,
    )
    with pytest.raises(DBAPIError) as captured:
        with engine.begin() as connection:
            connection.execute(_DIRECT_INSERT, facts)
    assert getattr(captured.value.orig, "sqlstate", None) == "23514"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "validator_set",
            '[{"implementation_digest":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","key":"validator.wrong",'
            '"semantic_version":"1.0.0"}]',
        ),
        ("validator_set_hash", "f" * 64),
    ],
)
def test_quality_report_insert_rejects_validator_set_not_declared_by_validate_node(
    migrated_database_url: str,
    field: str,
    value: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded, quality_node_id, source_version_id = _seed_valid_quality_node(factory)
    facts = _load_report_facts(
        engine,
        node_run_id=quality_node_id,
        source_version_id=source_version_id,
        created_by=seeded.actor.principal_id,
    )
    facts[field] = value

    with pytest.raises(DBAPIError) as captured:
        with engine.begin() as connection:
            connection.execute(_DIRECT_INSERT, facts)
    assert getattr(captured.value.orig, "sqlstate", None) == "23514"


def _seed_valid_quality_node(factory: sessionmaker[Session]):
    seeded = _seed_runtime(factory)
    with factory() as session, session.begin():
        upstream = session.get(ArtifactVersion, seeded.upstream_version_id)
        upstream_artifact = session.get(
            Artifact,
            upstream.artifact_id if upstream is not None else None,
        )
        assert upstream is not None and upstream_artifact is not None
        source = _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            upstream_artifact.content_definition_version_id,
            artifact_key="quality-source",
            artifact_type="lesson_division",
            branch_key="project",
            lesson_unit_id=None,
            content=dict(upstream.content_json),
        )
        workflow = WorkflowRuntimeService(session, seeded.actor)
        node = workflow.create_project_node_run(
            seeded.workflow_run_id,
            node_key="lesson.division.validate",
            status=NodeStatus.READY,
        )
        workflow.add_input_snapshot(
            node.id,
            input_key="artifact:lesson_division",
            source_type="artifact",
            source_id=source.artifact_id,
            source_version_id=source.id,
            content_hash=source.content_hash,
            snapshot=dict(source.content_json),
        )
    return seeded, node.id, source.id


def _load_report_facts(
    engine: Engine,
    *,
    node_run_id: UUID,
    source_version_id: UUID,
    created_by: UUID,
) -> dict[str, object]:
    with engine.connect() as connection:
        facts = dict(
            connection.execute(
                text(
                    """
                    SELECT
                        artifact_versions.organization_id,
                        workflow_runs.project_id,
                        artifacts.lesson_unit_id,
                        artifact_versions.id AS source_artifact_version_id,
                        artifact_versions.content_hash AS source_content_hash,
                        workflow_runs.content_release_id,
                        workflow_runs.workflow_definition_version_id,
                        node_runs.id AS validate_node_run_id
                    FROM artifact_versions
                    JOIN artifacts ON artifacts.id = artifact_versions.artifact_id
                    JOIN node_runs ON node_runs.id = :node_run_id
                    JOIN workflow_runs ON workflow_runs.id = node_runs.workflow_run_id
                    WHERE artifact_versions.id = :source_version_id
                    """
                ),
                {
                    "node_run_id": node_run_id,
                    "source_version_id": source_version_id,
                },
            )
            .mappings()
            .one()
        )
    validator_set, validator_set_hash = _validator_facts()
    facts.update(
        report_id=REPORT_ID,
        validator_set=validator_set,
        validator_set_hash=validator_set_hash,
        evidence_hash="c" * 64,
        created_by=created_by,
    )
    return facts


def _validator_facts() -> tuple[str, str]:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(CATALOG.read_text(encoding="utf-8")))
    binding = resolve_quality_report_binding(registered, "lesson.division.validate")
    payload = json.dumps(
        validator_set_payload(binding.validator_refs),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return payload, binding.validator_set_hash
