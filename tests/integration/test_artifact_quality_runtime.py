from __future__ import annotations

import json
from collections.abc import Callable
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
from apps.api.artifact_quality.repository import ArtifactQualityReportRepository
from apps.api.artifact_quality.service import ArtifactQualityError, ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import (
    ArtifactQualityTransactionError,
    SqlAlchemyArtifactQualityTransactionFactory,
)
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import ActorContext
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry, OutboxEvent
from apps.api.workflows.models import NodeRun
from apps.api.workflows.service import WorkflowRuntimeService
from tests.integration.test_node_execution_runtime import (
    _seed_approved_artifact,  # pyright: ignore[reportPrivateUsage]
    _seed_runtime,  # pyright: ignore[reportPrivateUsage]
)
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
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 1
        stored = ArtifactQualityReportRepository(session, seeded.actor).get_exact(
            project_id=seeded.project_id,
            source_artifact_version_id=seeded.source_version_id,
            workflow_definition_version_id=_workflow_version_id(session, seeded.node_run_id),
            validator_set_hash=_binding().validator_set_hash,
        )
        assert stored is not None and stored.id == first.report_id
        assert (
            ArtifactQualityReportRepository(session, seeded.actor).get_exact(
                project_id=seeded.project_id,
                source_artifact_version_id=seeded.source_version_id,
                workflow_definition_version_id=_workflow_version_id(session, seeded.node_run_id),
                validator_set_hash="f" * 64,
            )
            is None
        )


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
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 1


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
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == 1


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

    with pytest.raises(ValueError):
        _service(factory, cross_project, passed=True).execute(node_run_id)

    with factory() as session:
        node = session.get(NodeRun, node_run_id)
        assert node is not None and node.status == NodeStatus.READY.value
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 0
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == 0


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
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 0


def _seed_quality_node(factory: sessionmaker[Session]) -> QualitySeed:
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
    return QualitySeed(
        actor=runtime.actor,
        project_id=runtime.project_id,
        node_run_id=node.id,
        source_version_id=source.id,
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


def _binding() -> QualityReportBinding:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(CATALOG.read_text(encoding="utf-8")))
    return resolve_quality_report_binding(registered, "lesson.division.validate")


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
