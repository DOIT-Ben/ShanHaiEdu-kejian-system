from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from uuid import UUID

import httpx
from pydantic import SecretStr
from sqlalchemy import func, select

from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.jobs.models import GenerationJob
from apps.api.lessons.models import LessonUnit
from apps.api.main import create_app
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.settings import Settings
from apps.api.workflows.models import NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import override_test_identity
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from workers.node_execution import execute_node_execution_job

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


async def test_intro_worker_persists_one_exact_nine_option_job_and_isolates_lessons(
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
            comment="Approve the exact division used by the Intro worker test.",
            request_id="r1-intro-worker-approve-division",
        )
    with factory() as session:
        first_lesson = session.scalar(
            select(LessonUnit).where(
                LessonUnit.project_id == prepared.project_id,
                LessonUnit.status == "active",
            )
        )
        assert first_lesson is not None
        first_lesson_id = first_lesson.id
        source_division_version_id = first_lesson.source_division_version_id

    second_lesson_id = UUID("01990000-0000-7000-8000-000000000235")
    with factory() as session, session.begin():
        session.add(
            LessonUnit(
                id=second_lesson_id,
                organization_id=prepared.actor.organization_id,
                project_id=prepared.project_id,
                lesson_key="LESSON-INTRO-ISOLATION-002",
                position=2,
                title="第二课时导入隔离",
                scope_summary="只用于验证三类九套 exact 查询不串课时",
                objective_summary="第二课时保持独立空状态",
                estimated_minutes=40,
                source_division_version_id=source_division_version_id,
                status="active",
                created_by=prepared.actor.principal_id,
                updated_by=prepared.actor.principal_id,
            )
        )

    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=SecretStr(migrated_database_url),
        session_access_code=None,
        session_allowed_origins=[],
        session_csrf_secret=None,
        session_teacher_principal_id=None,
    )
    app = create_app(settings=settings, object_storage=FakeObjectStorage())
    override_test_identity(app, prepared.actor)
    transport = httpx.ASGITransport(app=app)
    provider = DeterministicNodeOutputProvider(outputs["intro.generate_options"])
    gateway = ModelGateway(
        {ModelCapability.TEXT_STRUCTURED_CREATIVE_EDUCATION: provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            prepared_node = await client.post(
                f"/api/v2/lessons/{first_lesson_id}/intro-options/node-runs",
                headers={"Idempotency-Key": "r1-intro-worker-prepare"},
                json={
                    "generation_mode": "default_nine",
                    "source_artifact_version_id": None,
                },
            )
            assert prepared_node.status_code == 200, prepared_node.text
            node_id = UUID(prepared_node.json()["data"]["id"])

            started = await client.post(
                f"/api/v2/node-runs/{node_id}/start",
                headers={"Idempotency-Key": "r1-intro-worker-start"},
                json={},
            )
            replayed = await client.post(
                f"/api/v2/node-runs/{node_id}/start",
                headers={"Idempotency-Key": "r1-intro-worker-start"},
                json={},
            )
            assert started.status_code == 202, started.text
            assert replayed.status_code == 202, replayed.text
            job_id = UUID(started.json()["data"]["job_id"])
            assert replayed.json()["data"]["job_id"] == str(job_id)

            outcome = await execute_node_execution_job(
                job_id,
                worker_id="r1-intro-worker-success",
                model=gateway,
                settings=settings,
            )
            with factory() as session:
                persisted_job = session.get(GenerationJob, job_id)
                persisted_node = session.get(NodeRun, node_id)
                attempts = session.scalars(
                    select(GenerationAttempt)
                    .where(GenerationAttempt.generation_job_id == job_id)
                    .order_by(GenerationAttempt.attempt_no)
                ).all()
                assert persisted_job is not None and persisted_node is not None
                failure_facts = {
                    "job_status": persisted_job.status,
                    "job_error": persisted_job.error_code,
                    "node_status": persisted_node.status,
                    "node_error": persisted_node.last_error_code,
                    "attempts": [
                        {"status": attempt.status, "error": attempt.error_code}
                        for attempt in attempts
                    ],
                }
            first_jobs = await client.get(
                f"/api/v2/projects/{prepared.project_id}/lessons/"
                f"{first_lesson_id}/intro-options/generation-jobs"
            )
            second_jobs = await client.get(
                f"/api/v2/projects/{prepared.project_id}/lessons/"
                f"{second_lesson_id}/intro-options/generation-jobs"
            )
            first_artifact = await client.get(
                f"/api/v2/projects/{prepared.project_id}/lessons/"
                f"{first_lesson_id}/intro-options/artifact"
            )
            second_artifact = await client.get(
                f"/api/v2/projects/{prepared.project_id}/lessons/"
                f"{second_lesson_id}/intro-options/artifact"
            )
    finally:
        app.state.database_engine.dispose()

    assert outcome == "succeeded", failure_facts
    assert provider.calls == 1
    assert first_jobs.status_code == 200, first_jobs.text
    assert second_jobs.status_code == 200, second_jobs.text
    assert [item["id"] for item in first_jobs.json()["data"]["items"]] == [str(job_id)]
    assert second_jobs.json()["data"]["items"] == []
    assert first_artifact.status_code == 200, first_artifact.text
    assert second_artifact.status_code == 200, second_artifact.text
    assert first_artifact.json()["data"]["artifact"] is not None
    assert second_artifact.json()["data"]["artifact"] is None

    with factory() as session:
        job = session.get(GenerationJob, job_id)
        assert job is not None
        assert job.project_id == prepared.project_id
        assert job.lesson_unit_id == first_lesson_id
        assert job.node_run_id == node_id
        assert job.result_artifact_version_id is not None
        version = session.get(ArtifactVersion, job.result_artifact_version_id)
        assert version is not None
        artifact = session.get(Artifact, version.artifact_id)
        assert artifact is not None
        assert artifact.project_id == prepared.project_id
        assert artifact.lesson_unit_id == first_lesson_id
        options = version.content_json["options"]
        assert len(options) == 9
        assert Counter(option["primary_tendency"] for option in options) == Counter(
            {"science": 3, "application": 3, "story": 3}
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(GenerationJob)
                .where(GenerationJob.node_run_id == node_id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(GenerationAttempt)
                .where(GenerationAttempt.generation_job_id == job_id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ArtifactVersion)
                .where(ArtifactVersion.source_node_run_id == node_id)
            )
            == 1
        )
    engine.dispose()
