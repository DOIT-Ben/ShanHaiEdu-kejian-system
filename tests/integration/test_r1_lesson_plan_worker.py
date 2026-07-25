from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import httpx
from pydantic import SecretStr
from sqlalchemy import func, select

from apps.api.artifacts.models import Artifact, ArtifactDraft, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.lessons.models import LessonUnit
from apps.api.main import create_app
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.settings import Settings
from apps.api.workflows.models import BranchRun, NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import override_test_identity
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from workers.node_execution import execute_node_execution_job

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


async def test_lesson_plan_job_worker_persists_exact_result_draft_and_cancellation(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    outputs = build_golden_branch_source_outputs(case)
    prepared = await _prepare_approval(factory, case, outputs["lesson.division.generate"])

    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="approve",
            comment="Approve the exact division used by the rescue worker test.",
            request_id="r1-rescue-worker-approve-division",
        )

    with factory() as session:
        existing_plan = session.scalar(
            select(NodeRun)
            .where(
                NodeRun.node_key == "lesson_plan.generate",
                NodeRun.status == "ready",
            )
            .order_by(NodeRun.id)
            .limit(1)
        )
        assert existing_plan is not None and existing_plan.branch_run_id is not None
        lesson_unit_id = session.scalar(
            select(BranchRun.lesson_unit_id).where(BranchRun.id == existing_plan.branch_run_id)
        )
        assert lesson_unit_id is not None

    second_lesson_id = new_uuid7()
    with factory() as session, session.begin():
        first_lesson = session.get(LessonUnit, lesson_unit_id)
        assert first_lesson is not None
        session.add(
            LessonUnit(
                id=second_lesson_id,
                organization_id=prepared.actor.organization_id,
                project_id=first_lesson.project_id,
                lesson_key="LESSON-RESCUE-002",
                position=2,
                title="第二课时隔离验证",
                scope_summary="仅用于证明 exact lesson 查询不串线",
                objective_summary="第二课时保持独立空状态",
                estimated_minutes=40,
                source_division_version_id=first_lesson.source_division_version_id,
                status="active",
                created_by=prepared.actor.principal_id,
                updated_by=prepared.actor.principal_id,
            )
        )

    settings = Settings(
        environment="test",
        database_url=SecretStr(migrated_database_url),
    )
    app = create_app(settings=settings, object_storage=FakeObjectStorage())
    override_test_identity(app, prepared.actor)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first_node_id, first_job_id = await _prepare_and_start(
                client,
                lesson_unit_id,
                key_suffix="success",
            )

            provider = DeterministicNodeOutputProvider(outputs["lesson_plan.generate"])
            gateway = ModelGateway(
                {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
                audit_sink=SqlAlchemyAttemptAuditSink(factory),
            )
            outcome = await execute_node_execution_job(
                first_job_id,
                worker_id="r1-rescue-node-worker-success",
                model=gateway,
                settings=settings,
            )
            with factory() as session:
                failed_job = session.get(GenerationJob, first_job_id)
                failed_node = session.get(NodeRun, first_node_id)
                assert failed_job is not None and failed_node is not None
                failure_facts = (
                    f"job_status={failed_job.status}, "
                    f"job_error={failed_job.error_code}, "
                    f"node_status={failed_node.status}, "
                    f"node_error={failed_node.last_error_code}"
                )
            assert outcome == "succeeded", failure_facts
            assert provider.calls == 1

            with factory() as session:
                job = session.get(GenerationJob, first_job_id)
                node = session.get(NodeRun, first_node_id)
                assert job is not None and node is not None
                assert job.status == "succeeded"
                assert job.lesson_unit_id == lesson_unit_id
                assert job.node_run_id == first_node_id
                assert job.result_artifact_version_id is not None
                assert node.status == "review_required"
                assert node.active_artifact_version_id == job.result_artifact_version_id
                result = session.get(ArtifactVersion, job.result_artifact_version_id)
                assert result is not None and result.source_node_run_id == first_node_id
                artifact = session.get(Artifact, result.artifact_id)
                assert artifact is not None and artifact.current_draft_id is not None
                draft = session.get(ArtifactDraft, artifact.current_draft_id)
                assert draft is not None
                assert draft.based_on_version_id == result.id
                assert draft.content_json == result.content_json
                attempt = session.scalar(
                    select(GenerationAttempt).where(
                        GenerationAttempt.node_run_id == first_node_id,
                        GenerationAttempt.status == "succeeded",
                    )
                )
                assert attempt is not None and attempt.generation_job_id == first_job_id
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(GenerationJob)
                        .where(GenerationJob.node_run_id == first_node_id)
                    )
                    == 1
                )

            first_jobs = await client.get(
                f"/api/v2/projects/{prepared.project_id}/lessons/"
                f"{lesson_unit_id}/lesson-plan/generation-jobs"
            )
            second_jobs = await client.get(
                f"/api/v2/projects/{prepared.project_id}/lessons/"
                f"{second_lesson_id}/lesson-plan/generation-jobs"
            )
            assert first_jobs.status_code == 200, first_jobs.text
            assert second_jobs.status_code == 200, second_jobs.text
            assert [item["id"] for item in first_jobs.json()["data"]["items"]] == [
                str(first_job_id)
            ]
            assert second_jobs.json()["data"]["items"] == []

            first_artifact = await client.get(
                f"/api/v2/projects/{prepared.project_id}/lessons/"
                f"{lesson_unit_id}/lesson-plan/artifact"
            )
            second_artifact = await client.get(
                f"/api/v2/projects/{prepared.project_id}/lessons/"
                f"{second_lesson_id}/lesson-plan/artifact"
            )
            assert first_artifact.status_code == 200, first_artifact.text
            assert second_artifact.status_code == 200, second_artifact.text
            assert first_artifact.json()["data"]["artifact"] is not None
            assert second_artifact.json()["data"]["artifact"] is None

            cancelled_node_id, cancelled_job_id = await _prepare_and_start(
                client,
                lesson_unit_id,
                key_suffix="cancelled",
            )
            cancelled = await client.post(
                f"/api/v2/generation-jobs/{cancelled_job_id}/cancel",
                headers={"Idempotency-Key": "r1-rescue-worker-cancel-job"},
            )
            assert cancelled.status_code == 202, cancelled.text

            unused_provider = DeterministicNodeOutputProvider(outputs["lesson_plan.generate"])
            unused_gateway = ModelGateway(
                {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: unused_provider},
                audit_sink=SqlAlchemyAttemptAuditSink(factory),
            )
            cancelled_outcome = await execute_node_execution_job(
                cancelled_job_id,
                worker_id="r1-rescue-node-worker-cancelled",
                model=unused_gateway,
                settings=settings,
            )
            assert cancelled_outcome == "cancelled"
            assert unused_provider.calls == 0

            with factory() as session:
                job = session.get(GenerationJob, cancelled_job_id)
                node = session.get(NodeRun, cancelled_node_id)
                assert job is not None and node is not None
                assert job.status == "cancelled"
                assert job.result_artifact_version_id is None
                assert node.status == "cancelled"
                assert node.active_artifact_version_id is None
    finally:
        app.state.database_engine.dispose()
        engine.dispose()


async def _prepare_and_start(
    client: httpx.AsyncClient,
    lesson_unit_id: UUID,
    *,
    key_suffix: str,
) -> tuple[UUID, UUID]:
    prepared = await client.post(
        f"/api/v2/lessons/{lesson_unit_id}/lesson-plan/node-runs",
        headers={"Idempotency-Key": f"r1-rescue-prepare-{key_suffix}"},
    )
    assert prepared.status_code == 200, prepared.text
    node_id = UUID(prepared.json()["data"]["id"])
    prepared_replay = await client.post(
        f"/api/v2/lessons/{lesson_unit_id}/lesson-plan/node-runs",
        headers={"Idempotency-Key": f"r1-rescue-prepare-{key_suffix}"},
    )
    assert prepared_replay.status_code == 200, prepared_replay.text
    assert UUID(prepared_replay.json()["data"]["id"]) == node_id
    started = await client.post(
        f"/api/v2/node-runs/{node_id}/start",
        headers={"Idempotency-Key": f"r1-rescue-start-{key_suffix}"},
    )
    assert started.status_code == 202, started.text
    job_id = UUID(started.json()["data"]["job_id"])
    started_replay = await client.post(
        f"/api/v2/node-runs/{node_id}/start",
        headers={"Idempotency-Key": f"r1-rescue-start-{key_suffix}"},
    )
    assert started_replay.status_code == 202, started_replay.text
    assert UUID(started_replay.json()["data"]["job_id"]) == job_id
    return node_id, job_id
