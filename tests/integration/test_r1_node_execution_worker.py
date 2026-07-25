from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select

from apps.api.artifacts.models import Artifact, ArtifactDraft, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.jobs.models import GenerationJob
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


async def test_node_execution_worker_persists_exact_result_and_cancellation(
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
            comment="Approve the exact division used by the R1 worker test.",
            request_id="r1-worker-approve-division",
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

    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=migrated_database_url,
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
                worker_id="r1-node-worker-success",
                model=gateway,
                settings=settings,
            )
            assert outcome == "succeeded"
            assert provider.calls == 1

            with factory() as session:
                job = session.get(GenerationJob, first_job_id)
                node = session.get(NodeRun, first_node_id)
                assert job is not None and node is not None
                assert job.status == "succeeded"
                assert job.result_artifact_version_id is not None
                assert node.status == "review_required"
                assert node.active_artifact_version_id == job.result_artifact_version_id
                result = session.get(ArtifactVersion, job.result_artifact_version_id)
                assert result is not None
                assert result.source_node_run_id == first_node_id
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
                assert attempt is not None
                assert attempt.generation_job_id == first_job_id

            cancelled_node_id, cancelled_job_id = await _prepare_and_start(
                client,
                lesson_unit_id,
                key_suffix="cancelled",
            )
            cancelled = await client.post(
                f"/api/v2/generation-jobs/{cancelled_job_id}/cancel",
                headers={"Idempotency-Key": "r1-worker-cancel-job"},
            )
            assert cancelled.status_code == 202, cancelled.text

            unused_provider = DeterministicNodeOutputProvider(outputs["lesson_plan.generate"])
            unused_gateway = ModelGateway(
                {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: unused_provider},
                audit_sink=SqlAlchemyAttemptAuditSink(factory),
            )
            cancelled_outcome = await execute_node_execution_job(
                cancelled_job_id,
                worker_id="r1-node-worker-cancelled",
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
        headers={"Idempotency-Key": f"r1-worker-prepare-{key_suffix}"},
    )
    assert prepared.status_code == 200, prepared.text
    node_id = UUID(prepared.json()["data"]["id"])
    started = await client.post(
        f"/api/v2/node-runs/{node_id}/start",
        headers={"Idempotency-Key": f"r1-worker-start-{key_suffix}"},
    )
    assert started.status_code == 202, started.text
    return node_id, UUID(started.json()["data"]["job_id"])
