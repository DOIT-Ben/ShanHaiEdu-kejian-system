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
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, system_actor
from apps.api.ids import new_uuid7
from apps.api.reliability.events import EventWriter
from apps.api.workflows.models import NodeRun
from apps.api.workflows.service import WorkflowRuntimeService
from tests.integration.test_node_execution_runtime import (
    _seed_runtime,  # pyright: ignore[reportPrivateUsage]
)
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"


@dataclass(frozen=True, slots=True)
class ApprovalSeed:
    actor: ActorContext
    project_id: UUID
    artifact_id: UUID
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
        assert artifact.current_approved_version_id is None
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
        assert artifact.current_approved_version_id is None
        assert _approval_count(session, seeded.version_id, "approve") == 0


def _seed_submitted_quality_artifact(
    factory: sessionmaker[Session],
) -> ApprovalSeed:
    runtime = _seed_runtime(factory)
    with factory() as session, session.begin():
        upstream = session.get(ArtifactVersion, runtime.upstream_version_id)
        upstream_artifact = session.get(
            Artifact,
            upstream.artifact_id if upstream is not None else None,
        )
        assert upstream is not None and upstream_artifact is not None
        artifact = Artifact(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            project_id=runtime.project_id,
            lesson_unit_id=None,
            branch_key="project",
            artifact_key=f"quality-review:{new_uuid7()}",
            artifact_type="lesson_division",
            content_definition_version_id=upstream_artifact.content_definition_version_id,
            status="in_review",
            stale_reason_json=None,
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(artifact)
        session.flush()
        version = ArtifactVersion(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            artifact_id=artifact.id,
            version_no=1,
            content_json=dict(runtime.output),
            content_hash=canonical_content_hash(runtime.output),
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
        artifact.current_submitted_version_id = version.id
        session.add(
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
            )
        )
        workflow = WorkflowRuntimeService(session, runtime.actor)
        node = workflow.create_project_node_run(
            runtime.workflow_run_id,
            node_key="lesson.division.validate",
            status=NodeStatus.READY,
        )
        workflow.add_input_snapshot(
            node.id,
            input_key="artifact:lesson_division",
            source_type="artifact",
            source_id=artifact.id,
            source_version_id=version.id,
            content_hash=version.content_hash,
            snapshot=dict(version.content_json),
        )
    return ApprovalSeed(
        actor=runtime.actor,
        project_id=runtime.project_id,
        artifact_id=artifact.id,
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
    return result.report_id


def _binding() -> QualityReportBinding:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(CATALOG.read_text(encoding="utf-8")))
    return resolve_quality_report_binding(registered, "lesson.division.validate")


def _approval_count(session: Session, version_id: UUID, action: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Approval)
            .where(Approval.artifact_version_id == version_id, Approval.action == action)
        )
        or 0
    )
