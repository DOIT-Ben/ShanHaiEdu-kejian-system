from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.artifact_quality.service import ArtifactQualityError, ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import SqlAlchemyArtifactQualityTransactionFactory
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.context import system_actor
from apps.api.identity.models import Organization
from apps.api.ids import new_uuid7
from apps.api.lessons.lesson_plan_runtime import LessonPlanRuntimeService
from apps.api.lessons.models import LessonUnit
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.workflows.models import BranchRun, NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from tests.integration.test_lesson_plan_runtime import (
    _open_gate,  # pyright: ignore[reportPrivateUsage]
    _prepare_generated_lesson_plan,  # pyright: ignore[reportPrivateUsage]
    _stage_and_validate,  # pyright: ignore[reportPrivateUsage]
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


async def test_two_lesson_plans_execute_and_review_without_cross_lesson_mutation(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    outputs = build_golden_branch_source_outputs(case)
    original_evidence = deepcopy(case["material_evidence"])
    second_evidence = deepcopy(original_evidence)
    evidence_mapping: dict[str, str] = {}
    for index, evidence in enumerate(second_evidence, start=5):
        original_key = evidence["evidence_key"]
        replacement_key = f"EV-MAT-{index:02d}"
        evidence["evidence_key"] = replacement_key
        evidence_mapping[original_key] = replacement_key
    case["material_evidence"].extend(second_evidence)
    division_output = deepcopy(outputs["lesson.division.generate"])
    first_lesson = division_output["lesson_units"][0]
    evidence_refs = list(first_lesson["evidence_refs"])
    second_lesson = deepcopy(first_lesson)
    second_lesson.update(
        lesson_unit_key="LESSON-002",
        position=2,
        title="1~5的认识练习",
        evidence_refs=[evidence_mapping[key] for key in evidence_refs],
    )
    division_output["lesson_units"].append(second_lesson)
    division_output["lesson_count"] = 2
    division = await _prepare_approval(factory, case, division_output)
    with factory() as session, session.begin():
        ArtifactService(session, division.actor).review(
            division.version_id,
            action="approve",
            comment="Approve two isolated lesson units.",
            request_id="issue-126-two-lessons",
        )

    with factory() as session:
        rows = session.execute(
            select(LessonUnit, NodeRun)
            .join(BranchRun, BranchRun.lesson_unit_id == LessonUnit.id)
            .join(NodeRun, NodeRun.branch_run_id == BranchRun.id)
            .where(NodeRun.node_key == "lesson_plan.generate")
        ).all()
        generate_by_lesson = {lesson.lesson_key: node.id for lesson, node in rows}
    assert set(generate_by_lesson) == {"LESSON-001", "LESSON-002"}

    first_output = deepcopy(outputs["lesson_plan.generate"])
    second_output = deepcopy(first_output)
    second_output["teaching_content"]["lesson_plan_key"] = "LESSON-PLAN-002"
    second_output["teaching_content"]["source_lesson_unit_key"] = "LESSON-002"
    second_output["teaching_content"]["lesson_topic"] = "1~5的认识练习"
    second_output["teaching_content"]["teaching_evidence_refs"] = [
        evidence_mapping[key] for key in evidence_refs
    ]
    for objective in second_output["teaching_objectives"]:
        objective["objective_evidence_refs"] = [
            evidence_mapping[key] for key in objective["objective_evidence_refs"]
        ]

    async def execute(lesson_key: str, output: dict[str, object]) -> ArtifactVersion:
        result = await NodeExecutionService(
            SqlAlchemyNodeExecutionTransactionFactory(factory, division.actor),
            ModelGateway(
                {
                    ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                        DeterministicNodeOutputProvider(output)
                    )
                },
                audit_sink=SqlAlchemyAttemptAuditSink(factory),
            ),
        ).execute(
            generate_by_lesson[lesson_key],
            request_id=f"issue-126-generate-{lesson_key.lower()}",
        )
        with factory() as session:
            version = session.get(ArtifactVersion, result.artifact_version_id)
            assert version is not None
            return version

    first_version, second_version = await asyncio.gather(
        execute("LESSON-001", first_output),
        execute("LESSON-002", second_output),
    )
    first_validate, _ = _stage_and_validate(factory, division.actor, first_version.id)
    second_validate, _ = _stage_and_validate(factory, division.actor, second_version.id)
    first_gate = _open_gate(factory, division.actor, first_version.id)
    second_gate = _open_gate(factory, division.actor, second_version.id)

    with factory() as session, session.begin():
        ArtifactService(session, division.actor).review(
            first_version.id,
            action="request_changes",
            comment="Return only lesson one.",
            request_id="issue-126-return-first",
        )
        ArtifactService(session, division.actor).review(
            second_version.id,
            action="approve",
            comment="Approve only lesson two.",
            request_id="issue-126-approve-second",
        )

    with factory() as session:
        first_artifact = session.get(Artifact, first_version.artifact_id)
        second_artifact = session.get(Artifact, second_version.artifact_id)
        assert first_artifact is not None and second_artifact is not None
        first_validate_node = session.get(NodeRun, first_validate)
        second_validate_node = session.get(NodeRun, second_validate)
        first_gate_node = session.get(NodeRun, first_gate)
        second_gate_node = session.get(NodeRun, second_gate)
        assert first_validate_node is not None
        assert second_validate_node is not None
        assert first_gate_node is not None
        assert second_gate_node is not None
        assert first_artifact.lesson_unit_id != second_artifact.lesson_unit_id
        assert first_artifact.status == "draft"
        assert second_artifact.status == "approved"
        assert second_artifact.current_approved_version_id == second_version.id
        assert first_validate_node.status == "approved"
        assert second_validate_node.status == "approved"
        assert first_gate_node.status == "skipped"
        assert second_gate_node.status == "approved"
        assert (
            session.scalar(
                select(func.count())
                .select_from(ArtifactQualityReport)
                .where(
                    ArtifactQualityReport.source_artifact_version_id.in_(
                        [first_version.id, second_version.id]
                    )
                )
            )
            == 2
        )


async def test_cross_tenant_and_revoked_division_fail_closed_before_quality_staging(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _prepare_generated_lesson_plan(factory)

    with factory() as session, session.begin():
        outsider_organization_id = new_uuid7()
        session.add(
            Organization(
                id=outsider_organization_id,
                slug=f"issue-126-{outsider_organization_id.hex[:12]}",
                name="Issue 126 outsider",
                status="active",
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        outsider = system_actor(outsider_organization_id)
        with pytest.raises(ApiError) as cross_tenant:
            LessonPlanRuntimeService(session, outsider).stage_quality(prepared.version_id)
        assert cross_tenant.value.code == "ARTIFACT_NOT_FOUND"

    with factory() as session, session.begin():
        lesson = session.scalar(
            select(LessonUnit).where(LessonUnit.organization_id == prepared.actor.organization_id)
        )
        assert lesson is not None
        ArtifactService(session, prepared.actor).review(
            lesson.source_division_version_id,
            action="revoke",
            comment="Withdraw the lesson division source.",
            request_id="issue-126-revoke-division",
        )

    with factory() as session:
        artifact = session.get(Artifact, prepared.artifact_id)
        assert artifact is not None
        assert artifact.status == "stale"

    with factory() as session:
        with pytest.raises(ApiError) as stale:
            with session.begin():
                LessonPlanRuntimeService(session, prepared.actor).stage_quality(prepared.version_id)
        assert stale.value.code == "LESSON_PLAN_RUNTIME_INVALID"


async def test_division_revoked_after_stage_cannot_produce_a_quality_report(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _prepare_generated_lesson_plan(factory)
    with factory() as session, session.begin():
        validate_id = LessonPlanRuntimeService(session, prepared.actor).stage_quality(
            prepared.version_id
        )
        lesson = session.scalar(
            select(LessonUnit).where(LessonUnit.organization_id == prepared.actor.organization_id)
        )
        assert lesson is not None
        division_version_id = lesson.source_division_version_id

    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            division_version_id,
            action="revoke",
            comment="Withdraw the frozen lesson division before validation.",
            request_id="issue-126-revoke-after-stage",
        )

    with pytest.raises(ArtifactQualityError) as caught:
        ArtifactQualityService(
            SqlAlchemyArtifactQualityTransactionFactory(factory, prepared.actor),
            runtime_quality_validator_registry(),
        ).execute(validate_id)
    assert caught.value.code == "QUALITY_SOURCE_SCOPE_INVALID"

    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ArtifactQualityReport)
                .where(ArtifactQualityReport.validate_node_run_id == validate_id)
            )
            == 0
        )
