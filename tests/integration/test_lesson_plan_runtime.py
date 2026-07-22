from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.artifact_quality.service import ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import SqlAlchemyArtifactQualityTransactionFactory
from apps.api.artifacts.authoring_provision import (
    ArtifactAuthoringProvisionPort,
    GeneratedDraftRequest,
)
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, system_actor
from apps.api.lessons.lesson_plan_runtime import LessonPlanRuntimeService
from apps.api.lessons.models import LessonUnit
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.prompt_runtime.models import ContextSnapshot
from apps.api.workflows.models import NodeInputSnapshot, NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


@dataclass(frozen=True, slots=True)
class PreparedLessonPlan:
    actor: ActorContext
    artifact_id: UUID
    version_id: UUID
    generate_node_id: UUID


async def test_lesson_plan_three_node_chain_uses_exact_lesson_and_material_scope(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    outputs = build_golden_branch_source_outputs(case)
    prepared = await _prepare_approval(factory, case, outputs["lesson.division.generate"])

    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="approve",
            comment="Approve the formal lesson division.",
            request_id="issue-126-approve-division",
        )

    with factory() as session:
        lesson = session.scalar(select(LessonUnit).where(LessonUnit.lesson_key == "LESSON-001"))
        assert lesson is not None
        generate = session.scalar(
            select(NodeRun).where(
                NodeRun.node_key == "lesson_plan.generate",
                NodeRun.status == "ready",
            )
        )
        assert generate is not None
        generate_id = generate.id
        division_version_id = lesson.source_division_version_id

    committed = await NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, prepared.actor),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                    DeterministicNodeOutputProvider(outputs["lesson_plan.generate"])
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    ).execute(generate_id, request_id="issue-126-generate")

    with factory() as session:
        division = session.execute(
            select(
                Artifact.status,
                Artifact.current_approved_version_id,
                Artifact.artifact_type,
                Artifact.branch_key,
                Artifact.lesson_unit_id,
            )
            .join(ArtifactVersion, ArtifactVersion.artifact_id == Artifact.id)
            .where(ArtifactVersion.id == division_version_id)
        ).one()
        assert division == (
            "approved",
            division_version_id,
            "lesson_division",
            "project",
            None,
        )
        context = session.scalar(
            select(ContextSnapshot).where(ContextSnapshot.node_run_id == generate_id)
        )
        assert context is not None
        bindings = {
            binding["source"]: binding["items"] for binding in context.bindings_json["bindings"]
        }
        assert set(bindings) == {
            "lesson_division.approved_version",
            "material.approved_parse",
            "material_scope.approved_version",
            "project.teacher_preferences",
        }
        lesson_context = bindings["lesson_division.approved_version"][0]["content"]
        assert lesson_context["lesson_unit"]["lesson_unit_key"] == "LESSON-001"
        assert "lesson_units" not in lesson_context
        assert len(bindings["material.approved_parse"]) == 1
        assert bindings["project.teacher_preferences"] == []

    with factory() as session, session.begin():
        validate_id = LessonPlanRuntimeService(session, prepared.actor).stage_quality(
            committed.artifact_version_id
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(NodeInputSnapshot)
                .where(NodeInputSnapshot.node_run_id == validate_id)
            )
            == 3
        )
        division_snapshot = session.scalar(
            select(NodeInputSnapshot).where(
                NodeInputSnapshot.node_run_id == validate_id,
                NodeInputSnapshot.input_key == "approval:lesson_division",
            )
        )
        assert division_snapshot is not None
        assert division_snapshot.snapshot_json["lesson_unit"]["lesson_unit_key"] == "LESSON-001"
        assert "lesson_units" not in division_snapshot.snapshot_json

    quality = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, prepared.actor),
        runtime_quality_validator_registry(),
    ).execute(validate_id)
    with factory() as session:
        report = session.get(ArtifactQualityReport, quality.report_id)
        assert report is not None
        assert quality.conclusion == "passed", report.findings_json

    with factory() as session, session.begin():
        gate_id = LessonPlanRuntimeService(session, prepared.actor).open_approval(
            committed.artifact_version_id
        )
        approval = ArtifactService(session, prepared.actor).review(
            committed.artifact_version_id,
            action="approve",
            comment="Approve the exact validated lesson plan.",
            request_id="issue-126-approve-plan",
        )

    with factory() as session:
        artifact_version = session.get(ArtifactVersion, committed.artifact_version_id)
        assert artifact_version is not None
        artifact = session.get(Artifact, artifact_version.artifact_id)
        assert artifact is not None
        generate_node = session.get(NodeRun, generate_id)
        validate_node = session.get(NodeRun, validate_id)
        gate_node = session.get(NodeRun, gate_id)
        approval_record = session.get(Approval, approval.id)
        assert generate_node is not None
        assert validate_node is not None
        assert gate_node is not None
        assert approval_record is not None
        assert artifact.current_approved_version_id == committed.artifact_version_id
        assert generate_node.status == "review_required"
        assert validate_node.status == "approved"
        assert gate_node.status == "approved"
        assert approval_record.quality_evidence_json["report_id"] == str(quality.report_id)
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 2
        assert session.scalar(select(func.count()).select_from(GenerationAttempt)) == 2
        assert session.scalar(select(func.count()).select_from(UsageRecord)) == 2


async def test_lesson_plan_return_edit_revalidate_and_approve_requires_new_exact_evidence(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _prepare_generated_lesson_plan(factory)
    first_validate_id, first_report_id = _stage_and_validate(
        factory,
        prepared.actor,
        prepared.version_id,
    )
    first_gate_id = _open_gate(factory, prepared.actor, prepared.version_id)

    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="request_changes",
            comment="Clarify the lesson topic without changing fixed lineage.",
            request_id="issue-126-request-changes-v1",
        )

    with factory() as session, session.begin():
        version = session.get(ArtifactVersion, prepared.version_id)
        assert version is not None
        draft = ArtifactAuthoringProvisionPort(
            session,
            system_actor(prepared.actor.organization_id),
        ).open_generated_draft(
            GeneratedDraftRequest(
                artifact_id=prepared.artifact_id,
                artifact_version_id=version.id,
                expected_content_hash=version.content_hash,
                draft_branch="main",
            )
        )
        draft_lock_version = draft.lock_version
        generated_content = deepcopy(version.content_json)

    forbidden = deepcopy(generated_content)
    forbidden["teaching_content"]["lesson_plan_key"] = "LESSON-PLAN-FORGED"
    with factory() as session:
        with pytest.raises(ApiError) as caught:
            with session.begin():
                ArtifactService(session, prepared.actor).save_draft(
                    prepared.artifact_id,
                    "main",
                    expected_lock_version=draft_lock_version,
                    content=forbidden,
                    request_id="issue-126-forbidden-edit",
                )
        assert caught.value.code == "AUTHORING_POLICY_VIOLATION"

    edited = deepcopy(generated_content)
    edited["teaching_content"]["lesson_topic"] = "1~5的认识与多种表征"
    with factory() as session, session.begin():
        saved = ArtifactService(session, prepared.actor).save_draft(
            prepared.artifact_id,
            "main",
            expected_lock_version=draft_lock_version,
            content=edited,
            request_id="issue-126-save-v2",
        )
        replacement = ArtifactService(session, prepared.actor).submit(
            prepared.artifact_id,
            "main",
            expected_lock_version=saved.lock_version,
            source_kind="manual",
            request_id="issue-126-submit-v2",
        )
        replacement_id = replacement.id

    with factory() as session:
        with pytest.raises(ApiError) as caught:
            with session.begin():
                ArtifactService(session, prepared.actor).review(
                    replacement_id,
                    action="approve",
                    comment="The old report must not approve this version.",
                    request_id="issue-126-reject-old-report",
                )
        assert caught.value.code == "ARTIFACT_QUALITY_REQUIRED"

    second_validate_id, second_report_id = _stage_and_validate(
        factory,
        prepared.actor,
        replacement_id,
    )
    second_gate_id = _open_gate(factory, prepared.actor, replacement_id)
    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            replacement_id,
            action="approve",
            comment="Approve the edited version with exact new evidence.",
            request_id="issue-126-approve-v2",
        )

    with factory() as session:
        artifact = session.get(Artifact, prepared.artifact_id)
        assert artifact is not None
        first_gate = session.get(NodeRun, first_gate_id)
        second_gate = session.get(NodeRun, second_gate_id)
        first_validate = session.get(NodeRun, first_validate_id)
        second_validate = session.get(NodeRun, second_validate_id)
        assert first_gate is not None
        assert second_gate is not None
        assert first_validate is not None
        assert second_validate is not None
        assert artifact.current_approved_version_id == replacement_id
        assert first_report_id != second_report_id
        assert first_gate.status == "skipped"
        assert second_gate.status == "approved"
        assert first_validate.run_no == 1
        assert second_validate.run_no == 2
        assert first_gate.run_no == 1
        assert second_gate.run_no == 2
        assert (
            session.scalar(
                select(func.count())
                .select_from(ArtifactVersion)
                .where(ArtifactVersion.artifact_id == prepared.artifact_id)
            )
            == 2
        )


async def _prepare_generated_lesson_plan(
    factory: sessionmaker[Session],
) -> PreparedLessonPlan:
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    outputs = build_golden_branch_source_outputs(case)
    division = await _prepare_approval(factory, case, outputs["lesson.division.generate"])
    with factory() as session, session.begin():
        ArtifactService(session, division.actor).review(
            division.version_id,
            action="approve",
            comment="Approve the formal lesson division.",
            request_id="issue-126-helper-approve-division",
        )
    with factory() as session:
        generate = session.scalar(
            select(NodeRun).where(
                NodeRun.node_key == "lesson_plan.generate",
                NodeRun.status == "ready",
            )
        )
        assert generate is not None
        generate_node_id = generate.id
    committed = await NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, division.actor),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                    DeterministicNodeOutputProvider(outputs["lesson_plan.generate"])
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    ).execute(generate_node_id, request_id="issue-126-helper-generate")
    with factory() as session:
        version = session.get(ArtifactVersion, committed.artifact_version_id)
        assert version is not None
        return PreparedLessonPlan(
            actor=division.actor,
            artifact_id=version.artifact_id,
            version_id=version.id,
            generate_node_id=generate_node_id,
        )


def _stage_and_validate(
    factory: sessionmaker[Session],
    actor: ActorContext,
    version_id: UUID,
) -> tuple[UUID, UUID]:
    with factory() as session, session.begin():
        validate_id = LessonPlanRuntimeService(session, actor).stage_quality(version_id)
    result = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, actor),
        runtime_quality_validator_registry(),
    ).execute(validate_id)
    with factory() as session:
        report = session.get(ArtifactQualityReport, result.report_id)
        assert report is not None
        assert result.conclusion == "passed", report.findings_json
    return validate_id, result.report_id


def _open_gate(
    factory: sessionmaker[Session],
    actor: ActorContext,
    version_id: UUID,
) -> UUID:
    with factory() as session, session.begin():
        return LessonPlanRuntimeService(session, actor).open_approval(version_id)
