from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.binding import QualityReportBinding, resolve_quality_report_binding
from apps.api.artifact_quality.contracts import (
    QualityConclusion,
    QualityValidationContext,
    ValidatorOutcome,
    ValidatorRef,
)
from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.registry import InMemoryQualityValidatorRegistry
from apps.api.artifact_quality.repository import ArtifactQualityReportRepository
from apps.api.artifact_quality.service import ArtifactQualityError, ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import (
    ArtifactQualityTransactionError,
    SqlAlchemyArtifactQualityTransactionFactory,
)
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.context import ActorContext, system_actor
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonUnit
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry, OutboxEvent
from apps.api.workflows.models import BranchRun, NodeRun, WorkflowRun
from apps.api.workflows.service import WorkflowRuntimeService
from tests.integration.test_node_execution_runtime import (
    _seed_approved_artifact,  # pyright: ignore[reportPrivateUsage]
    _seed_runtime,  # pyright: ignore[reportPrivateUsage]
)
from workers.artifact_quality import execute_artifact_quality_node
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"


@dataclass(frozen=True, slots=True)
class QualitySeed:
    actor: ActorContext
    project_id: UUID
    node_run_id: UUID
    source_version_id: UUID


@dataclass
class FixtureValidator:
    ref: ValidatorRef
    passed: bool = True

    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        return ValidatorOutcome(
            validator=self.ref,
            passed=self.passed,
            findings=() if self.passed else ({"code": "FIXTURE_QUALITY_FAILED"},),
            evidence={"source_content_hash": context.source_content_hash},
        )


@dataclass
class CrashingValidator:
    ref: ValidatorRef

    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        raise RuntimeError(f"fixture validator crashed for {context.node_run_id}")


def test_quality_report_success_exact_query_and_replay_are_one_atomic_fact(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory)
    service = _service(factory, seeded, passed=True)

    first = service.execute(seeded.node_run_id)
    replay = service.execute(seeded.node_run_id)

    assert replay == first
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.APPROVED.value
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 1
        assert _event_count(session, "artifact.quality_validation.queued") == 1
        assert _event_count(session, "artifact.quality_report.passed") == 1
        assert _outbox_count(session, "artifact.quality_validation.queued") == 1
        assert _outbox_count(session, "artifact.quality_report.passed") == 1
        stored = ArtifactQualityReportRepository(session, seeded.actor).get_exact(
            project_id=seeded.project_id,
            source_type="artifact",
            source_version_id=seeded.source_version_id,
            workflow_definition_version_id=_workflow_version_id(session, seeded.node_run_id),
            validator_set_hash=_binding().validator_set_hash,
        )
        assert stored is not None and stored.id == first.report_id
        source = session.get(ArtifactVersion, seeded.source_version_id)
        run = session.get(WorkflowRun, node.workflow_run_id)
        binding = _binding()
        assert source is not None and run is not None
        assert stored.organization_id == seeded.actor.organization_id
        assert stored.project_id == seeded.project_id
        assert stored.lesson_unit_id is None
        assert stored.source_type == "artifact"
        assert stored.source_artifact_version_id == source.id
        assert stored.source_file_asset_version_id is None
        assert stored.source_content_hash == source.content_hash
        assert stored.content_release_id == run.content_release_id
        assert stored.workflow_definition_version_id == run.workflow_definition_version_id
        assert stored.validate_node_run_id == node.id
        assert stored.validator_set_hash == binding.validator_set_hash
        assert stored.validator_set_json == [asdict(item) for item in binding.validator_refs]
        assert stored.conclusion == "passed"
        assert stored.findings_json == []
        assert len(stored.evidence_hash) == 64
        assert stored.created_by == seeded.actor.principal_id
        assert (
            ArtifactQualityReportRepository(session, seeded.actor).get_exact(
                project_id=seeded.project_id,
                source_type="artifact",
                source_version_id=seeded.source_version_id,
                workflow_definition_version_id=_workflow_version_id(session, seeded.node_run_id),
                validator_set_hash="f" * 64,
            )
            is None
        )


@pytest.mark.parametrize(
    ("node_key", "input_ref", "branch_key", "asset_kind", "mime_type"),
    [
        (
            "ppt.final.validate",
            "asset:pptx",
            "ppt",
            "pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
        (
            "video.technical.validate",
            "asset:video_final",
            "video",
            "video_final",
            "video/mp4",
        ),
    ],
)
def test_published_media_quality_nodes_persist_exact_file_asset_report(
    migrated_database_url: str,
    node_key: str,
    input_ref: str,
    branch_key: str,
    asset_kind: str,
    mime_type: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_asset_quality_node(
        factory,
        node_key=node_key,
        input_ref=input_ref,
        branch_key=branch_key,
        asset_kind=asset_kind,
        mime_type=mime_type,
    )
    binding = _binding(node_key)
    registry = InMemoryQualityValidatorRegistry(
        {ref: FixtureValidator(ref) for ref in binding.validator_refs}
    )

    result = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, seeded.actor),
        registry,
    ).execute(seeded.node_run_id)

    assert result.conclusion == "passed"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        report = session.get(ArtifactQualityReport, result.report_id)
        version = session.get(FileAssetVersion, seeded.source_version_id)
        assert node is not None and node.status == NodeStatus.APPROVED.value
        assert report is not None and version is not None
        assert report.source_type == "asset"
        assert report.source_artifact_version_id is None
        assert report.source_file_asset_version_id == version.id
        assert report.source_content_hash == version.sha256
        stored = ArtifactQualityReportRepository(session, seeded.actor).get_exact(
            project_id=seeded.project_id,
            source_type="asset",
            source_version_id=version.id,
            workflow_definition_version_id=_workflow_version_id(session, seeded.node_run_id),
            validator_set_hash=binding.validator_set_hash,
        )
        assert stored is not None and stored.id == report.id


def test_quality_failure_persists_failed_report_and_failed_node(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory)

    result = _service(factory, seeded, passed=False).execute(seeded.node_run_id)

    assert result.conclusion == "failed"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        report = session.get(ArtifactQualityReport, result.report_id)
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert report is not None and report.conclusion == "failed"
        assert report.findings_json[0]["finding"]["code"] == "FIXTURE_QUALITY_FAILED"


def test_worker_composition_executes_the_queued_quality_node(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory)
    binding = _binding()
    registry = InMemoryQualityValidatorRegistry(
        {ref: FixtureValidator(ref) for ref in binding.validator_refs}
    )

    result = execute_artifact_quality_node(
        migrated_database_url,
        seeded.node_run_id,
        registry,
    )

    assert result is not None and result.conclusion == "passed"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.APPROVED.value
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 1


def test_not_ready_quality_node_queues_once_when_it_becomes_ready(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory, status=NodeStatus.NOT_READY)

    with factory() as session:
        assert _event_count(session, "artifact.quality_validation.queued") == 0
        assert _outbox_count(session, "artifact.quality_validation.queued") == 0

    with factory() as session, session.begin():
        WorkflowRuntimeService(session, seeded.actor).transition_node(
            seeded.node_run_id,
            NodeStatus.READY,
        )

    with factory() as session:
        assert _event_count(session, "artifact.quality_validation.queued") == 1
        assert _outbox_count(session, "artifact.quality_validation.queued") == 1

    binding = _binding()
    registry = InMemoryQualityValidatorRegistry(
        {ref: FixtureValidator(ref) for ref in binding.validator_refs}
    )
    result = execute_artifact_quality_node(
        migrated_database_url,
        seeded.node_run_id,
        registry,
    )

    assert result is not None and result.conclusion == "passed"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.APPROVED.value


def test_validator_technical_failure_fails_node_without_quality_report(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory)
    binding = _binding()
    registry = InMemoryQualityValidatorRegistry(
        {
            ref: (CrashingValidator(ref) if index == 0 else FixtureValidator(ref))
            for index, ref in enumerate(binding.validator_refs)
        }
    )
    service = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, seeded.actor),
        registry,
    )

    with pytest.raises(ArtifactQualityError) as captured:
        service.execute(seeded.node_run_id)

    assert captured.value.code == "QUALITY_VALIDATION_TECHNICAL_FAILURE"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 0
        assert _event_count(session, "artifact.quality_validation.technical_failed") == 1
        assert _outbox_count(session, "artifact.quality_validation.technical_failed") == 1


def test_prepare_hash_failure_fails_node_without_quality_report(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory, snapshot_hash="f" * 64)

    with pytest.raises(ArtifactQualityError) as captured:
        _service(factory, seeded, passed=True).execute(seeded.node_run_id)

    assert captured.value.code == "QUALITY_SOURCE_HASH_MISMATCH"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert node.last_error_code == "QUALITY_SOURCE_HASH_MISMATCH"
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 0
        assert _event_count(session, "artifact.quality_validation.technical_failed") == 1
        assert _outbox_count(session, "artifact.quality_validation.technical_failed") == 1


def test_same_identity_from_another_node_with_different_payload_is_a_stable_conflict(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory)
    _service(factory, seeded, passed=True).execute(seeded.node_run_id)
    second_node_id = _create_replay_node(factory, seeded)
    second = QualitySeed(
        actor=seeded.actor,
        project_id=seeded.project_id,
        node_run_id=second_node_id,
        source_version_id=seeded.source_version_id,
    )

    with pytest.raises(ArtifactQualityError) as captured:
        _service(factory, second, passed=False).execute(second_node_id)

    assert captured.value.code == "QUALITY_REPORT_IDEMPOTENCY_CONFLICT"
    with factory() as session:
        node = session.get(NodeRun, second_node_id)
        assert node is not None and node.status == NodeStatus.READY.value
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 1
        assert _event_count(session, "artifact.quality_report.passed") == 1


def test_concurrent_payloads_for_one_identity_return_one_report_and_one_stable_conflict(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory)
    worker_actor = system_actor(seeded.actor.organization_id)
    transactions = SqlAlchemyArtifactQualityTransactionFactory(factory, worker_actor)
    with transactions.begin() as transaction:
        context = transaction.prepare(seeded.node_run_id)
    passed_outcomes = tuple(
        FixtureValidator(ref).validate(context) for ref in context.validator_refs
    )
    failed_outcomes = tuple(
        FixtureValidator(ref, passed=False).validate(context) for ref in context.validator_refs
    )
    barrier = Barrier(2)

    def complete(
        task: tuple[
            QualityValidationContext,
            QualityConclusion,
            tuple[ValidatorOutcome, ...],
        ],
    ):
        task_context, conclusion, outcomes = task
        try:
            barrier.wait(timeout=10)
            with transactions.begin() as transaction:
                return transaction.complete(
                    task_context,
                    conclusion=conclusion,
                    outcomes=outcomes,
                )
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                complete,
                (
                    (context, "passed", passed_outcomes),
                    (context, "failed", failed_outcomes),
                ),
            )
        )

    reports = [item for item in results if not isinstance(item, Exception)]
    errors = [item for item in results if isinstance(item, ArtifactQualityTransactionError)]
    diagnostics = [
        (type(item).__name__, getattr(item, "code", None), repr(item.__cause__))
        for item in results
        if isinstance(item, Exception)
    ]
    assert len(reports) == 1, diagnostics
    assert len(errors) == 1
    assert errors[0].code == "QUALITY_REPORT_IDEMPOTENCY_CONFLICT"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 1


def test_cross_project_source_is_rejected_before_report_or_node_write(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory)
    node_run_id = _create_cross_project_source_node(factory, seeded)
    cross_project = QualitySeed(
        actor=seeded.actor,
        project_id=seeded.project_id,
        node_run_id=node_run_id,
        source_version_id=seeded.source_version_id,
    )

    with pytest.raises(ArtifactQualityError) as captured:
        _service(factory, cross_project, passed=True).execute(node_run_id)

    assert captured.value.code == "QUALITY_SOURCE_SCOPE_INVALID"
    with factory() as session:
        node = session.get(NodeRun, node_run_id)
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 0
        assert _event_count(session, "artifact.quality_report.passed") == 0
        assert _event_count(session, "artifact.quality_validation.technical_failed") == 1


def test_transaction_rejects_a_conclusion_that_disagrees_with_validator_outcomes(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory)
    transactions = SqlAlchemyArtifactQualityTransactionFactory(factory, seeded.actor)

    with pytest.raises(ArtifactQualityTransactionError) as captured:
        with transactions.begin() as transaction:
            context = transaction.prepare(seeded.node_run_id)
            outcomes = tuple(
                FixtureValidator(ref).validate(context) for ref in context.validator_refs
            )
            transaction.complete(context, conclusion="failed", outcomes=outcomes)

    assert captured.value.code == "QUALITY_CONCLUSION_MISMATCH"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.READY.value
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 0


@pytest.mark.parametrize("fault_stage", ["after_report", "after_terminal", "after_event"])
def test_any_quality_commit_fault_rolls_back_report_node_and_events(
    migrated_database_url: str,
    fault_stage: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_quality_node(factory)

    def fail(stage: str) -> None:
        if stage == fault_stage:
            raise RuntimeError(f"injected {stage}")

    service = _service(factory, seeded, passed=True, fault_injector=fail)
    with pytest.raises(ArtifactQualityError) as captured:
        service.execute(seeded.node_run_id)

    assert captured.value.code == "QUALITY_REPORT_COMMIT_FAILED"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.READY.value
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 0
        assert _event_count(session, "artifact.quality_report.passed") == 0
        assert _outbox_count(session, "artifact.quality_report.passed") == 0


def _seed_quality_node(
    factory: sessionmaker[Session],
    *,
    status: NodeStatus = NodeStatus.READY,
    snapshot_hash: str | None = None,
) -> QualitySeed:
    runtime = _seed_runtime(factory)
    with factory() as session, session.begin():
        upstream_artifact = session.get(
            Artifact, _artifact_id(session, runtime.upstream_version_id)
        )
        assert upstream_artifact is not None
        source = _seed_approved_artifact(
            session,
            runtime.actor,
            runtime.project_id,
            upstream_artifact.content_definition_version_id,
            artifact_key="lesson-division",
            artifact_type="lesson_division",
            branch_key="project",
            lesson_unit_id=None,
            content=runtime.output,
        )
        workflow = WorkflowRuntimeService(session, runtime.actor)
        node = workflow.create_project_node_run(
            runtime.workflow_run_id,
            node_key="lesson.division.validate",
            status=status,
        )
        workflow.add_input_snapshot(
            node.id,
            input_key="artifact:lesson_division",
            source_type="artifact",
            source_id=source.artifact_id,
            source_version_id=source.id,
            content_hash=snapshot_hash or source.content_hash,
            snapshot=dict(source.content_json),
        )
    return QualitySeed(
        actor=runtime.actor,
        project_id=runtime.project_id,
        node_run_id=node.id,
        source_version_id=source.id,
    )


def _seed_asset_quality_node(
    factory: sessionmaker[Session],
    *,
    node_key: str,
    input_ref: str,
    branch_key: str,
    asset_kind: str,
    mime_type: str,
) -> QualitySeed:
    runtime = _seed_runtime(factory)
    with factory() as session, session.begin():
        run = session.get(WorkflowRun, runtime.workflow_run_id)
        assert run is not None
        lesson = LessonUnit(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            project_id=runtime.project_id,
            lesson_key=f"QUALITY-{branch_key.upper()}",
            position=1,
            title=f"{branch_key} quality fixture",
            scope_summary="Exact media quality source",
            objective_summary="Persist a media quality report",
            estimated_minutes=40,
            source_division_version_id=runtime.upstream_version_id,
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
            branch_key=branch_key,
            status="active",
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(branch)
        asset = FileAsset(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            asset_key=f"quality-{asset_kind}:{runtime.project_id}",
            asset_kind=asset_kind,
            current_version_id=None,
            status="active",
            retention_class="project",
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(asset)
        session.flush()
        version = FileAssetVersion(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            file_asset_id=asset.id,
            version_no=1,
            storage_bucket="test-only",
            storage_key=f"quality/{runtime.project_id}/{asset_kind}",
            mime_type=mime_type,
            byte_size=1024,
            sha256="d" * 64,
            etag=f"quality-{asset_kind}",
            width=1280 if mime_type == "video/mp4" else None,
            height=720 if mime_type == "video/mp4" else None,
            duration_ms=60_000 if mime_type == "video/mp4" else None,
            page_count=10 if asset_kind == "pptx" else None,
            scan_status="clean",
            metadata_json={"asset_kind": asset_kind},
            derived_from_version_id=None,
            created_at=utc_now(),
            created_by=runtime.actor.principal_id,
        )
        session.add(version)
        session.flush()
        asset.current_version_id = version.id
        node = NodeRun(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            workflow_run_id=run.id,
            branch_run_id=branch.id,
            node_key=node_key,
            run_no=1,
            status=NodeStatus.READY.value,
            trigger_type="manual",
            automation_policy_snapshot_json=run.automation_policy_snapshot_json,
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(node)
        session.flush()
        WorkflowRuntimeService(session, runtime.actor).add_input_snapshot(
            node.id,
            input_key=input_ref,
            source_type="asset",
            source_id=asset.id,
            source_version_id=version.id,
            content_hash=version.sha256,
            snapshot={
                "mime_type": version.mime_type,
                "byte_size": version.byte_size,
                "sha256": version.sha256,
            },
        )
    return QualitySeed(
        actor=runtime.actor,
        project_id=runtime.project_id,
        node_run_id=node.id,
        source_version_id=version.id,
    )


def _service(
    factory: sessionmaker[Session],
    seeded: QualitySeed,
    *,
    passed: bool,
    fault_injector: Callable[[str], None] | None = None,
) -> ArtifactQualityService:
    binding = _binding()
    registry = InMemoryQualityValidatorRegistry(
        {ref: FixtureValidator(ref, passed=passed) for ref in binding.validator_refs}
    )
    return ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(
            factory,
            seeded.actor,
            fault_injector=fault_injector,
        ),
        registry,
    )


def _create_replay_node(factory: sessionmaker[Session], seeded: QualitySeed) -> UUID:
    with factory() as session, session.begin():
        first_node = session.get(NodeRun, seeded.node_run_id)
        source = session.get(ArtifactVersion, seeded.source_version_id)
        assert first_node is not None and source is not None
        workflow = WorkflowRuntimeService(session, seeded.actor)
        node = workflow.create_project_node_run(
            first_node.workflow_run_id,
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
    return node.id


def _create_cross_project_source_node(
    factory: sessionmaker[Session],
    seeded: QualitySeed,
) -> UUID:
    with factory() as session, session.begin():
        first_node = session.get(NodeRun, seeded.node_run_id)
        source = session.get(ArtifactVersion, seeded.source_version_id)
        source_artifact = session.get(Artifact, source.artifact_id if source is not None else None)
        assert first_node is not None and source is not None and source_artifact is not None
        other_project = ProjectRepository(session, seeded.actor).create(
            CreateProjectRequest(title="Other project", knowledge_point="Isolation")
        )
        foreign_source = _seed_approved_artifact(
            session,
            seeded.actor,
            other_project.id,
            source_artifact.content_definition_version_id,
            artifact_key="foreign-lesson-division",
            artifact_type="lesson_division",
            branch_key="project",
            lesson_unit_id=None,
            content=dict(source.content_json),
        )
        workflow = WorkflowRuntimeService(session, seeded.actor)
        node = workflow.create_project_node_run(
            first_node.workflow_run_id,
            node_key="lesson.division.validate",
            status=NodeStatus.READY,
        )
        workflow.add_input_snapshot(
            node.id,
            input_key="artifact:lesson_division",
            source_type="artifact",
            source_id=foreign_source.artifact_id,
            source_version_id=foreign_source.id,
            content_hash=foreign_source.content_hash,
            snapshot=dict(foreign_source.content_json),
        )
    return node.id


def _binding(node_key: str = "lesson.division.validate") -> QualityReportBinding:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(CATALOG.read_text(encoding="utf-8")))
    return resolve_quality_report_binding(registered, node_key)


def _artifact_id(session: Session, version_id: UUID) -> UUID:
    from apps.api.artifacts.models import ArtifactVersion

    version = session.get(ArtifactVersion, version_id)
    assert version is not None
    return version.artifact_id


def _workflow_version_id(session: Session, node_run_id: UUID) -> UUID:
    from apps.api.workflows.models import WorkflowRun

    node = session.get(NodeRun, node_run_id)
    assert node is not None
    run = session.get(WorkflowRun, node.workflow_run_id)
    assert run is not None
    return run.workflow_definition_version_id


def _event_count(session: Session, event_type: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(EventStreamEntry)
            .where(EventStreamEntry.event_type == event_type)
        )
        or 0
    )


def _outbox_count(session: Session, topic: str) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.topic == topic)
        )
        or 0
    )
