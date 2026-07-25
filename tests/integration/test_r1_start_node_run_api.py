from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import func, select

from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.main import create_app
from apps.api.reliability.models import OutboxEvent
from apps.api.settings import Settings
from apps.api.workflows.models import BranchRun, NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import override_test_identity
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


async def test_start_node_run_queues_one_exact_job_and_rejects_conflicts(
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
            comment="Approve the exact division used by the R1 start command test.",
            request_id="r1-start-approve-division",
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

    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=migrated_database_url,
        ),
        object_storage=FakeObjectStorage(),
    )
    override_test_identity(app, prepared.actor)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            plan = await client.post(
                f"/api/v2/lessons/{lesson_unit_id}/lesson-plan/node-runs",
                headers={"Idempotency-Key": "r1-start-plan-prepare-001"},
            )
            assert plan.status_code == 200, plan.text
            plan_node_id = UUID(plan.json()["data"]["id"])

            intro = await client.post(
                f"/api/v2/lessons/{lesson_unit_id}/intro-options/node-runs",
                headers={"Idempotency-Key": "r1-start-intro-prepare-001"},
                json={"generation_mode": "default_nine"},
            )
            assert intro.status_code == 200, intro.text
            intro_node_id = UUID(intro.json()["data"]["id"])

            revision = "Keep the approved lesson scope and foreground manipulatives."
            started = await client.post(
                f"/api/v2/node-runs/{plan_node_id}/start",
                headers={"Idempotency-Key": "r1-start-node-001"},
                json={"user_revision": revision},
            )
            assert started.status_code == 202, started.text
            started_data = started.json()["data"]
            job_id = UUID(started_data["job_id"])
            assert started_data == {
                "job_id": str(job_id),
                "status": "queued",
                "events_url": f"/api/v2/generation-jobs/{job_id}/events/stream",
            }

            replay = await client.post(
                f"/api/v2/node-runs/{plan_node_id}/start",
                headers={"Idempotency-Key": "r1-start-node-001"},
                json={"user_revision": revision},
            )
            assert replay.status_code == 202, replay.text
            assert replay.json()["data"] == started_data

            not_ready = await client.post(
                f"/api/v2/node-runs/{plan_node_id}/start",
                headers={"Idempotency-Key": "r1-start-node-002"},
            )
            assert not_ready.status_code == 409, not_ready.text
            assert not_ready.json()["error"]["code"] == "NODE_RUN_NOT_READY"

            with factory() as session, session.begin():
                session.add(
                    GenerationJob(
                        id=new_uuid7(),
                        organization_id=prepared.actor.organization_id,
                        project_id=prepared.project_id,
                        source_material_id=None,
                        node_run_id=intro_node_id,
                        lesson_unit_id=lesson_unit_id,
                        result_artifact_version_id=None,
                        creation_prompt_version_id=None,
                        creation_batch_id=None,
                        creation_request_json={},
                        job_type="workflow.node",
                        status="queued",
                        progress_percent=0,
                        progress_message="Queued for node execution",
                        error_code=None,
                        idempotency_key="seed-active-node-job",
                        request_hash="0" * 64,
                        priority=100,
                        attempt_count=0,
                        created_by=prepared.actor.principal_id,
                        updated_by=prepared.actor.principal_id,
                    )
                )

            active_conflict = await client.post(
                f"/api/v2/node-runs/{intro_node_id}/start",
                headers={"Idempotency-Key": "r1-start-node-active"},
            )
            assert active_conflict.status_code == 409, active_conflict.text
            assert active_conflict.json()["error"]["code"] == "NODE_RUN_JOB_ACTIVE"

            invalid_body = await client.post(
                f"/api/v2/node-runs/{intro_node_id}/start",
                headers={"Idempotency-Key": "r1-start-node-invalid"},
                json={"provider": "browser-forged"},
            )
            assert invalid_body.status_code == 422, invalid_body.text
            assert invalid_body.json()["error"]["code"] == "VALIDATION_FAILED"

            too_long = await client.post(
                f"/api/v2/node-runs/{intro_node_id}/start",
                headers={"Idempotency-Key": "r1-start-node-too-long"},
                json={"user_revision": "x" * 6001},
            )
            assert too_long.status_code == 422, too_long.text

        with factory() as session:
            job = session.get(GenerationJob, job_id)
            node = session.get(NodeRun, plan_node_id)
            assert job is not None and node is not None
            assert job.organization_id == prepared.actor.organization_id
            assert job.project_id == prepared.project_id
            assert job.node_run_id == plan_node_id
            assert job.lesson_unit_id == lesson_unit_id
            assert job.result_artifact_version_id is None
            assert job.job_type == "workflow.node"
            assert job.status == "queued"
            assert job.creation_request_json == {"user_revision": revision}
            assert node.status == "queued"
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(GenerationJob)
                    .where(GenerationJob.node_run_id == plan_node_id)
                )
                == 1
            )
            queued_event = session.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_type == "generation_job",
                    OutboxEvent.aggregate_id == job_id,
                    OutboxEvent.topic == "generation.job.queued",
                )
            )
            assert queued_event is not None
    finally:
        app.state.database_engine.dispose()
        engine.dispose()
