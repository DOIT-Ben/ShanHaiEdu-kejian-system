from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import func, select

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.artifact_quality.service import ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import SqlAlchemyArtifactQualityTransactionFactory
from apps.api.artifacts.models import Approval, Artifact
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.lessons.lesson_plan_runtime import LessonPlanRuntimeService
from apps.api.reliability.models import EventStreamEntry
from apps.api.workflows.approval_port import (
    ArtifactApprovalGateCommand,
    WorkflowArtifactApprovalPort,
)
from apps.api.workflows.models import NodeRun
from tests.integration.test_lesson_plan_runtime import (
    _open_gate,  # pyright: ignore[reportPrivateUsage]
    _prepare_generated_lesson_plan,  # pyright: ignore[reportPrivateUsage]
    _stage_and_validate,  # pyright: ignore[reportPrivateUsage]
)


async def test_concurrent_stage_open_and_approve_share_one_exact_runtime_fact(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _prepare_generated_lesson_plan(factory)

    stage_barrier = Barrier(2)

    def stage() -> UUID:
        stage_barrier.wait(timeout=30)
        with factory() as session, session.begin():
            return LessonPlanRuntimeService(session, prepared.actor).stage_quality(
                prepared.version_id
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(stage) for _ in range(2)]
        validate_ids = [future.result(timeout=60) for future in futures]
    assert validate_ids[0] == validate_ids[1]

    quality = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, prepared.actor),
        runtime_quality_validator_registry(),
    ).execute(validate_ids[0])
    assert quality.conclusion == "passed"

    open_barrier = Barrier(2)

    def open_gate() -> UUID:
        open_barrier.wait(timeout=30)
        with factory() as session, session.begin():
            return LessonPlanRuntimeService(session, prepared.actor).open_approval(
                prepared.version_id
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(open_gate) for _ in range(2)]
        gate_ids = [future.result(timeout=60) for future in futures]
    assert gate_ids[0] == gate_ids[1]

    approve_barrier = Barrier(2)

    def approve(request_id: str) -> UUID:
        approve_barrier.wait(timeout=30)
        with factory() as session, session.begin():
            return (
                ArtifactService(session, prepared.actor)
                .review(
                    prepared.version_id,
                    action="approve",
                    comment="Concurrent exact approval.",
                    request_id=request_id,
                )
                .id
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(approve, "issue-126-concurrent-approve-a"),
            executor.submit(approve, "issue-126-concurrent-approve-b"),
        ]
        approval_ids = [future.result(timeout=60) for future in futures]
    assert approval_ids[0] == approval_ids[1]

    with factory() as session:
        generate_node = session.get(NodeRun, prepared.generate_node_id)
        assert generate_node is not None
        branch_run_id = generate_node.branch_run_id
        assert (
            session.scalar(
                select(func.count())
                .select_from(NodeRun)
                .where(
                    NodeRun.branch_run_id == branch_run_id,
                    NodeRun.node_key == "lesson_plan.validate",
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(NodeRun)
                .where(
                    NodeRun.branch_run_id == branch_run_id,
                    NodeRun.node_key == "lesson_plan.approve",
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Approval)
                .where(
                    Approval.artifact_version_id == prepared.version_id,
                    Approval.action == "approve",
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ArtifactQualityReport)
                .where(ArtifactQualityReport.source_artifact_version_id == prepared.version_id)
            )
            == 1
        )


async def test_gate_completion_failure_rolls_back_artifact_approval_and_event(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _prepare_generated_lesson_plan(factory)
    _stage_and_validate(factory, prepared.actor, prepared.version_id)
    gate_id = _open_gate(factory, prepared.actor, prepared.version_id)
    original = WorkflowArtifactApprovalPort.complete

    def fail_after_gate(
        port: WorkflowArtifactApprovalPort,
        command: ArtifactApprovalGateCommand,
    ) -> None:
        original(port, command)
        raise RuntimeError("approval gate completion fault")

    monkeypatch.setattr(WorkflowArtifactApprovalPort, "complete", fail_after_gate)
    with factory() as session:
        with pytest.raises(RuntimeError, match="approval gate completion fault"):
            with session.begin():
                ArtifactService(session, prepared.actor).review(
                    prepared.version_id,
                    action="approve",
                    comment="Must roll back all approval facts.",
                    request_id="issue-126-gate-fault",
                )

    with factory() as session:
        artifact = session.get(Artifact, prepared.artifact_id)
        assert artifact is not None
        assert artifact.status == "in_review"
        assert artifact.current_submitted_version_id == prepared.version_id
        assert artifact.current_approved_version_id is None
        gate = session.get(NodeRun, gate_id)
        assert gate is not None
        assert gate.status == "review_required"
        assert (
            session.scalar(
                select(func.count())
                .select_from(Approval)
                .where(
                    Approval.artifact_version_id == prepared.version_id,
                    Approval.action == "approve",
                )
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(EventStreamEntry)
                .where(
                    EventStreamEntry.resource_id == prepared.artifact_id,
                    EventStreamEntry.event_type == "artifact.version.approved",
                )
            )
            == 0
        )
