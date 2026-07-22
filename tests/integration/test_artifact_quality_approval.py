from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.binding import QualityReportBinding, resolve_quality_report_binding
from apps.api.artifact_quality.contracts import (
    QualityValidationContext,
    ValidatorOutcome,
    ValidatorRef,
)
from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.registry import InMemoryQualityValidatorRegistry
from apps.api.artifact_quality.service import ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import SqlAlchemyArtifactQualityTransactionFactory
from apps.api.artifacts.domain import ApprovalAction, canonical_content_hash
from apps.api.artifacts.models import Approval, Artifact, ArtifactDraft, ArtifactVersion
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.artifacts.service import ArtifactService
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, system_actor
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonUnit
from apps.api.reliability.events import EventWriter
from apps.api.reliability.models import EventStreamEntry, OutboxEvent
from apps.api.workflows.models import BranchRun, NodeRun, WorkflowRun
from apps.api.workflows.service import WorkflowRuntimeService
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.integration.test_node_execution_runtime import (
    _seed_approved_artifact,  # pyright: ignore[reportPrivateUsage]
    _seed_runtime,  # pyright: ignore[reportPrivateUsage]
)
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


@dataclass(frozen=True, slots=True)
class ApprovalSeed:
    actor: ActorContext
    project_id: UUID
    artifact_id: UUID
    prior_approved_version_id: UUID
    version_id: UUID
    validate_node_id: UUID


@dataclass(frozen=True, slots=True)
class PassingValidator:
    ref: ValidatorRef
    passed: bool = True

    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        return ValidatorOutcome(
            validator=self.ref,
            passed=self.passed,
            findings=() if self.passed else ({"code": "FIXTURE_QUALITY_FAILED"},),
            evidence={"source_content_hash": context.source_content_hash},
        )


def test_quality_gated_approval_rejects_missing_report_without_partial_writes(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_submitted_quality_artifact(factory)

    with factory() as session:
        with pytest.raises(ApiError) as captured:
            with session.begin():
                ArtifactService(session, seeded.actor).review(
                    seeded.version_id,
                    action="approve",
                    comment="No report",
                    request_id="req-quality-missing",
                )
        assert captured.value.code == "ARTIFACT_QUALITY_REQUIRED"
        artifact = session.get(Artifact, seeded.artifact_id)
        assert artifact is not None
        assert artifact.status == "in_review"
        assert artifact.current_submitted_version_id == seeded.version_id
        assert artifact.current_approved_version_id == seeded.prior_approved_version_id
        assert _approval_count(session, seeded.version_id, "approve") == 0


def test_failed_report_blocks_approve_but_does_not_block_request_changes(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_submitted_quality_artifact(factory)
    _execute_report(factory, seeded, passed=False)

    with factory() as session:
        with pytest.raises(ApiError) as captured:
            with session.begin():
                ArtifactService(session, seeded.actor).review(
                    seeded.version_id,
                    action="approve",
                    comment="Failed report",
                    request_id="req-quality-failed",
                )
        assert captured.value.code == "ARTIFACT_QUALITY_FAILED"

        with session.begin():
            returned = ArtifactService(session, seeded.actor).review(
                seeded.version_id,
                action="request_changes",
                comment="Repair the findings",
                request_id="req-quality-return",
            )
        artifact = session.get(Artifact, seeded.artifact_id)
        assert artifact is not None and artifact.status == "draft"
        assert artifact.current_submitted_version_id is None
        assert returned.quality_evidence_json == {}


@pytest.mark.parametrize("as_system", [False, True])
def test_exact_passing_report_is_server_bound_for_user_and_system_approval(
    migrated_database_url: str,
    as_system: bool,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_submitted_quality_artifact(factory)
    report_id = _execute_report(factory, seeded, passed=True)
    reviewer = system_actor(seeded.actor.organization_id) if as_system else seeded.actor

    with factory() as session, session.begin():
        approval = ArtifactService(session, reviewer).review(
            seeded.version_id,
            action="approve",
            comment="Exact report",
            request_id=f"req-quality-pass-{as_system}",
        )
        report = session.get(ArtifactQualityReport, report_id)
        assert report is not None
        assert approval.quality_evidence_json == {
            "report_id": str(report.id),
            "evidence_hash": report.evidence_hash,
        }


def test_report_for_old_version_cannot_unlock_a_new_submission(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_submitted_quality_artifact(factory)
    _execute_report(factory, seeded, passed=True)

    with factory() as session, session.begin():
        artifact = session.get(Artifact, seeded.artifact_id)
        old = session.get(ArtifactVersion, seeded.version_id)
        assert artifact is not None and old is not None
        replacement = ArtifactVersion(
            id=new_uuid7(),
            organization_id=old.organization_id,
            artifact_id=old.artifact_id,
            version_no=old.version_no + 1,
            content_json=dict(old.content_json) | {"summary": "new submission"},
            content_hash=canonical_content_hash(
                dict(old.content_json) | {"summary": "new submission"}
            ),
            render_summary_json={},
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=seeded.actor.principal_id,
        )
        session.add(replacement)
        session.flush()
        artifact.current_submitted_version_id = replacement.id
        session.add(
            Approval(
                id=new_uuid7(),
                organization_id=old.organization_id,
                artifact_version_id=replacement.id,
                node_run_id=None,
                action=ApprovalAction.SUBMIT.value,
                actor_type="user",
                actor_user_id=seeded.actor.user_id,
                comment=None,
                quality_evidence_json={},
                policy_snapshot_json={},
                created_by=seeded.actor.principal_id,
            )
        )
        replacement_id = replacement.id

    with factory() as session:
        with pytest.raises(ApiError) as captured:
            with session.begin():
                ArtifactService(session, seeded.actor).review(
                    replacement_id,
                    action="approve",
                    comment="Old evidence must not apply",
                    request_id="req-quality-old-report",
                )
        assert captured.value.code == "ARTIFACT_QUALITY_REQUIRED"


def test_passing_report_with_nonapproved_validate_node_is_rejected(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_submitted_quality_artifact(factory)
    _execute_report(factory, seeded, passed=True)
    with factory() as session, session.begin():
        node = session.get(NodeRun, seeded.validate_node_id)
        assert node is not None
        node.status = NodeStatus.FAILED.value
        node.last_error_code = "SIMULATED_POST_REPORT_FAILURE"

    with factory() as session:
        with pytest.raises(ApiError) as captured:
            with session.begin():
                ArtifactService(session, seeded.actor).review(
                    seeded.version_id,
                    action="approve",
                    comment="Node terminal mismatch",
                    request_id="req-quality-node-mismatch",
                )
        assert captured.value.code == "ARTIFACT_QUALITY_REPORT_INVALID"


def test_concurrent_exact_approvals_return_one_server_bound_record(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_submitted_quality_artifact(factory)
    report_id = _execute_report(factory, seeded, passed=True)

    def approve(request_id: str) -> tuple[UUID, dict[str, object]]:
        with factory() as session, session.begin():
            approval = ArtifactService(session, seeded.actor).review(
                seeded.version_id,
                action="approve",
                comment="Concurrent exact report",
                request_id=request_id,
            )
            return approval.id, dict(approval.quality_evidence_json)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(approve, ("req-quality-double-1", "req-quality-double-2")))

    assert results[0] == results[1]
    assert results[0][1]["report_id"] == str(report_id)
    with factory() as session:
        assert _approval_count(session, seeded.version_id, "approve") == 1


def test_event_failure_rolls_back_quality_bound_approval(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_submitted_quality_artifact(factory)
    _execute_report(factory, seeded, passed=True)
    with factory() as session, session.begin():
        source = session.get(ArtifactVersion, seeded.version_id)
        source_artifact = session.get(
            Artifact,
            source.artifact_id if source is not None else None,
        )
        assert source is not None and source_artifact is not None
        downstream = _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            source_artifact.content_definition_version_id,
            artifact_key="quality-rollback-downstream",
            artifact_type="lesson_division",
            branch_key="project",
            lesson_unit_id=None,
            content=dict(source.content_json),
        )
        ArtifactRelationService(session, seeded.actor).add(
            from_version_id=seeded.prior_approved_version_id,
            to_version_id=downstream.id,
            relation_type="derives_from",
            binding_key="quality-rollback",
            impact_scope={"mode": "all"},
        )
        downstream_artifact_id = downstream.artifact_id
        baseline_events = _count(session, EventStreamEntry)
        baseline_outbox = _count(session, OutboxEvent)

    def fail_event(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated event failure")

    monkeypatch.setattr(EventWriter, "append", fail_event)
    with factory() as session:
        with pytest.raises(RuntimeError, match="simulated event failure"):
            with session.begin():
                ArtifactService(session, seeded.actor).review(
                    seeded.version_id,
                    action="approve",
                    comment="Must roll back",
                    request_id="req-quality-event-failure",
                )
        session.expire_all()
        artifact = session.get(Artifact, seeded.artifact_id)
        assert artifact is not None
        assert artifact.status == "in_review"
        assert artifact.current_submitted_version_id == seeded.version_id
        assert artifact.current_approved_version_id == seeded.prior_approved_version_id
        assert _approval_count(session, seeded.version_id, "approve") == 0
        downstream_artifact = session.get(Artifact, downstream_artifact_id)
        assert downstream_artifact is not None
        assert downstream_artifact.status == "approved"
        assert downstream_artifact.stale_reason_json is None
        assert _count(session, EventStreamEntry) == baseline_events
        assert _count(session, OutboxEvent) == baseline_outbox


def _seed_submitted_quality_artifact(
    factory: sessionmaker[Session],
) -> ApprovalSeed:
    runtime = _seed_runtime(factory)
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    outputs = build_golden_branch_source_outputs(case)
    lesson_plan_content = outputs["lesson_plan.generate"]
    division_content = outputs["lesson.division.generate"]
    division_lesson_key = division_content["lesson_units"][0]["lesson_unit_key"]
    with factory() as session, session.begin():
        upstream = session.get(ArtifactVersion, runtime.upstream_version_id)
        upstream_artifact = session.get(
            Artifact,
            upstream.artifact_id if upstream is not None else None,
        )
        assert upstream is not None and upstream_artifact is not None
        definition = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.definition_key == "lesson_plan.generate.output"
            )
        )
        division_definition = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.definition_key == "lesson.division.generate.output"
            )
        )
        run = session.get(WorkflowRun, runtime.workflow_run_id)
        assert definition is not None and division_definition is not None and run is not None
        division_artifact = Artifact(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            project_id=runtime.project_id,
            lesson_unit_id=None,
            branch_key="project",
            artifact_key=f"quality-division:{new_uuid7()}",
            artifact_type="lesson_division",
            content_definition_version_id=division_definition.id,
            status="approved",
            stale_reason_json=None,
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(division_artifact)
        session.flush()
        division_version = ArtifactVersion(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            artifact_id=division_artifact.id,
            version_no=1,
            content_json=division_content,
            content_hash=canonical_content_hash(division_content),
            render_summary_json={},
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=runtime.actor.principal_id,
        )
        session.add(division_version)
        session.flush()
        division_artifact.current_approved_version_id = division_version.id
        lesson = LessonUnit(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            project_id=runtime.project_id,
            lesson_key=division_lesson_key,
            position=1,
            title="Quality approval fixture",
            scope_summary="Exercise the generic artifact quality approval guard",
            objective_summary="Keep declared lesson division completion out of this fixture",
            estimated_minutes=40,
            source_division_version_id=division_version.id,
            status="active",
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(lesson)
        session.flush()
        branch = BranchRun(
            id=new_uuid7(),
            workflow_run_id=run.id,
            lesson_unit_id=lesson.id,
            branch_key="lesson_plan",
            status="active",
            started_at=utc_now(),
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(branch)
        session.flush()
        artifact = Artifact(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            project_id=runtime.project_id,
            lesson_unit_id=lesson.id,
            branch_key="lesson_plan",
            artifact_key=f"quality-review:{new_uuid7()}",
            artifact_type="lesson_plan",
            content_definition_version_id=definition.id,
            status="in_review",
            stale_reason_json=None,
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(artifact)
        session.flush()
        prior_content = dict(lesson_plan_content)
        prior_content["material_analysis"] = dict(prior_content["material_analysis"])
        prior_content["material_analysis"]["teaching_value"] = (
            f"{prior_content['material_analysis']['teaching_value']} (previous draft)"
        )
        prior = ArtifactVersion(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            artifact_id=artifact.id,
            version_no=1,
            content_json=prior_content,
            content_hash=canonical_content_hash(prior_content),
            render_summary_json={},
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=runtime.actor.principal_id,
        )
        session.add(prior)
        session.flush()
        version = ArtifactVersion(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            artifact_id=artifact.id,
            version_no=2,
            content_json=dict(lesson_plan_content),
            content_hash=canonical_content_hash(lesson_plan_content),
            render_summary_json={},
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=runtime.actor.principal_id,
        )
        session.add(version)
        session.flush()
        draft = ArtifactDraft(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            artifact_id=artifact.id,
            draft_branch="main",
            content_json=dict(version.content_json),
            validation_report_json={"valid": True},
            based_on_version_id=version.id,
            autosaved_at=utc_now(),
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(draft)
        session.flush()
        artifact.current_draft_id = draft.id
        artifact.current_approved_version_id = prior.id
        artifact.current_submitted_version_id = version.id
        session.add_all(
            [
                Approval(
                    id=new_uuid7(),
                    organization_id=runtime.actor.organization_id,
                    artifact_version_id=prior.id,
                    node_run_id=None,
                    action=ApprovalAction.APPROVE.value,
                    actor_type="user",
                    actor_user_id=runtime.actor.user_id,
                    comment="Historical fixture approval",
                    quality_evidence_json={"fixture": "pre-guard"},
                    policy_snapshot_json={},
                    created_by=runtime.actor.principal_id,
                ),
                Approval(
                    id=new_uuid7(),
                    organization_id=runtime.actor.organization_id,
                    artifact_version_id=version.id,
                    node_run_id=None,
                    action=ApprovalAction.SUBMIT.value,
                    actor_type="user",
                    actor_user_id=runtime.actor.user_id,
                    comment=None,
                    quality_evidence_json={},
                    policy_snapshot_json={},
                    created_by=runtime.actor.principal_id,
                ),
            ]
        )
        workflow = WorkflowRuntimeService(session, runtime.actor)
        node = NodeRun(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            workflow_run_id=run.id,
            branch_run_id=branch.id,
            node_key="lesson_plan.validate",
            run_no=1,
            status=NodeStatus.READY.value,
            trigger_type="manual",
            automation_policy_snapshot_json=run.automation_policy_snapshot_json,
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(node)
        session.flush()
        workflow.add_input_snapshot(
            node.id,
            input_key="artifact:lesson_plan",
            source_type="artifact",
            source_id=artifact.id,
            source_version_id=version.id,
            content_hash=version.content_hash,
            snapshot=dict(version.content_json),
        )
        workflow.add_input_snapshot(
            node.id,
            input_key="approval:lesson_division",
            source_type="artifact",
            source_id=division_artifact.id,
            source_version_id=division_version.id,
            content_hash=division_version.content_hash,
            snapshot=dict(division_version.content_json),
        )
        workflow.add_input_snapshot(
            node.id,
            input_key="content:material_evidence",
            source_type="material_parse",
            source_id=runtime.source_material_id,
            source_version_id=runtime.material_parse_version_id,
            content_hash=runtime.material_evidence_hash,
            snapshot=dict(runtime.material_evidence),
        )
    return ApprovalSeed(
        actor=runtime.actor,
        project_id=runtime.project_id,
        artifact_id=artifact.id,
        prior_approved_version_id=prior.id,
        version_id=version.id,
        validate_node_id=node.id,
    )


def _execute_report(
    factory: sessionmaker[Session],
    seeded: ApprovalSeed,
    *,
    passed: bool,
) -> UUID:
    binding = _binding()
    registry = InMemoryQualityValidatorRegistry(
        {ref: PassingValidator(ref, passed=passed) for ref in binding.validator_refs}
    )
    result = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, seeded.actor),
        registry,
    ).execute(seeded.validate_node_id)
    if passed:
        with factory() as session, session.begin():
            validate = session.get(NodeRun, seeded.validate_node_id)
            version = session.get(ArtifactVersion, seeded.version_id)
            report = session.get(ArtifactQualityReport, result.report_id)
            artifact = session.get(Artifact, seeded.artifact_id)
            assert validate is not None and validate.branch_run_id is not None
            assert version is not None and report is not None and artifact is not None
            if (
                artifact.current_submitted_version_id != version.id
                or artifact.status != "in_review"
            ):
                return result.report_id
            workflow = WorkflowRuntimeService(session, seeded.actor)
            gate = workflow.create_branch_node_run(
                validate.workflow_run_id,
                validate.branch_run_id,
                node_key="lesson_plan.approve",
                status=NodeStatus.NOT_READY,
            )
            workflow.add_input_snapshot(
                gate.id,
                input_key="artifact:lesson_plan",
                source_type="artifact",
                source_id=seeded.artifact_id,
                source_version_id=version.id,
                content_hash=version.content_hash,
                snapshot=dict(version.content_json),
            )
            workflow.add_input_snapshot(
                gate.id,
                input_key="report:lesson_plan_quality",
                source_type="quality_report",
                source_id=report.id,
                source_version_id=report.id,
                content_hash=report.evidence_hash,
                snapshot={"report_id": str(report.id), "evidence_hash": report.evidence_hash},
            )
            workflow.transition_node(gate.id, NodeStatus.READY)
            workflow.transition_node(gate.id, NodeStatus.DRAFT)
            workflow.transition_node(gate.id, NodeStatus.REVIEW_REQUIRED)
    return result.report_id


def _binding() -> QualityReportBinding:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(CATALOG.read_text(encoding="utf-8")))
    return resolve_quality_report_binding(registered, "lesson_plan.validate")


def _approval_count(session: Session, version_id: UUID, action: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Approval)
            .where(Approval.artifact_version_id == version_id, Approval.action == action)
        )
        or 0
    )


def _count(session: Session, model: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)
