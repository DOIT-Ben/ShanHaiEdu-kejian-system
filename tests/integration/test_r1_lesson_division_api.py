from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.artifacts.models import ArtifactVersion
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_session_factory
from apps.api.identity.models import Organization
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.lessons.models import LessonUnit
from apps.api.main import create_app
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.projects.models import Project
from apps.api.settings import Settings
from apps.api.workflows.artifact_input_selection import ArtifactInputSelectionReader
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.conftest import run_migration
from tests.fakes.identity import (
    configure_test_identity,
    override_test_identity,
    seed_test_actor,
)
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_r1_material_scope_api import _seed_material_parse
from workers.artifact_quality import execute_artifact_quality_node
from workers.node_execution import execute_node_execution_job

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


async def test_lesson_division_prepare_start_and_refresh_are_exact(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=postgres_database_url,
        session_access_code=None,
        session_allowed_origins=[],
        session_csrf_secret=None,
        session_teacher_principal_id=None,
    )
    app = create_app(
        settings=settings,
        object_storage=FakeObjectStorage(),
    )
    actor = configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_id, material_id, parse_id = await _project_with_material(
                client,
                app,
                actor,
                idempotency_key="r1-division-project-001",
                title="认识1到5",
            )
            other_project_id, _, _ = await _project_with_material(
                client,
                app,
                actor,
                idempotency_key="r1-division-project-002",
                title="认识6到10",
            )

            materials = await client.get(f"/api/v2/projects/{project_id}/materials")
            assert materials.status_code == 200, materials.text
            assert [item["id"] for item in materials.json()["data"]["items"]] == [str(material_id)]
            other_materials = await client.get(f"/api/v2/projects/{other_project_id}/materials")
            assert material_id not in {
                UUID(item["id"]) for item in other_materials.json()["data"]["items"]
            }

            scope = await client.post(
                f"/api/v2/projects/{project_id}/material-scope/versions",
                headers={"Idempotency-Key": "r1-division-scope-001"},
                json={
                    "source_material_id": str(material_id),
                    "material_parse_version_id": str(parse_id),
                    "page_start": 2,
                    "page_end": 2,
                },
            )
            assert scope.status_code == 201, scope.text
            scope_version_id = UUID(scope.json()["data"]["current_submitted_version"]["id"])
            approval = await client.post(
                f"/api/v2/artifact-versions/{scope_version_id}/approvals",
                headers={"Idempotency-Key": "r1-division-scope-approve-001"},
                json={"action": "approve", "comment": "范围确认"},
            )
            assert approval.status_code == 201, approval.text

            restored_scope = await client.get(
                f"/api/v2/projects/{project_id}/material-scope/artifact"
            )
            assert restored_scope.status_code == 200, restored_scope.text
            assert restored_scope.json()["data"]["artifact"]["current_approved_version"][
                "id"
            ] == str(scope_version_id)

            cross_project = await client.post(
                f"/api/v2/projects/{other_project_id}/lesson-division/node-runs",
                headers={"Idempotency-Key": "r1-division-cross-project-001"},
                json={"material_scope_artifact_version_id": str(scope_version_id)},
            )
            assert cross_project.status_code == 409
            assert cross_project.json()["error"]["code"] == "LESSON_DIVISION_RUNTIME_INVALID"

            prepared = await client.post(
                f"/api/v2/projects/{project_id}/lesson-division/node-runs",
                headers={"Idempotency-Key": "r1-division-prepare-001"},
                json={"material_scope_artifact_version_id": str(scope_version_id)},
            )
            assert prepared.status_code == 200, prepared.text
            prepared_data = prepared.json()["data"]
            assert prepared_data["node_key"] == "lesson.division.generate"
            assert prepared_data["status"] == "ready"
            node_run_id = UUID(prepared_data["id"])

            replay = await client.post(
                f"/api/v2/projects/{project_id}/lesson-division/node-runs",
                headers={"Idempotency-Key": "r1-division-prepare-001"},
                json={"material_scope_artifact_version_id": str(scope_version_id)},
            )
            assert replay.status_code == 200
            assert replay.json()["data"]["id"] == str(node_run_id)

            factory = build_session_factory(app.state.database_engine)
            with factory() as session:
                assert ArtifactInputSelectionReader(session, actor).for_node(node_run_id) == {
                    "approval:material_scope": scope_version_id
                }

            started = await client.post(
                f"/api/v2/node-runs/{node_run_id}/start",
                headers={"Idempotency-Key": "r1-division-start-001"},
                json={},
            )
            assert started.status_code == 202, started.text
            job_id = UUID(started.json()["data"]["job_id"])
            started_replay = await client.post(
                f"/api/v2/node-runs/{node_run_id}/start",
                headers={"Idempotency-Key": "r1-division-start-001"},
                json={},
            )
            assert started_replay.status_code == 202
            assert started_replay.json()["data"]["job_id"] == str(job_id)

            jobs = await client.get(
                f"/api/v2/projects/{project_id}/lesson-division/generation-jobs"
            )
            assert jobs.status_code == 200, jobs.text
            assert [item["id"] for item in jobs.json()["data"]["items"]] == [str(job_id)]
            job = jobs.json()["data"]["items"][0]
            assert job["project_id"] == str(project_id)
            assert job["lesson_unit_id"] is None
            assert job["workflow_node_key"] == "lesson.division.generate"

            division = await client.get(f"/api/v2/projects/{project_id}/lesson-division/artifact")
            assert division.status_code == 200, division.text
            assert division.json()["data"]["artifact"] is None

            case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
            output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
            output["lesson_units"][0]["evidence_refs"] = ["p2-text-1", "p2-image-1"]
            provider = DeterministicNodeOutputProvider(output)
            outcome = await execute_node_execution_job(
                job_id,
                worker_id="r1-division-worker-success",
                model=ModelGateway(
                    {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
                    audit_sink=SqlAlchemyAttemptAuditSink(factory),
                ),
                settings=settings,
            )
            assert outcome == "succeeded"
            assert provider.calls == 1

            restored_jobs = await client.get(
                f"/api/v2/projects/{project_id}/lesson-division/generation-jobs"
            )
            assert restored_jobs.status_code == 200, restored_jobs.text
            restored_job = restored_jobs.json()["data"]["items"][0]
            assert restored_job["id"] == str(job_id)
            assert restored_job["status"] == "succeeded"
            assert restored_job["result_artifact_version_id"] is not None

            restored_division = await client.get(
                f"/api/v2/projects/{project_id}/lesson-division/artifact"
            )
            assert restored_division.status_code == 200, restored_division.text
            restored_artifact = restored_division.json()["data"]["artifact"]
            assert restored_artifact is not None
            assert (
                restored_artifact["current_submitted_version"]["id"]
                == restored_job["result_artifact_version_id"]
            )

            artifact_id = restored_artifact["id"]
            editable = await client.get(f"/api/v2/artifacts/{artifact_id}")
            assert editable.status_code == 200, editable.text
            edited_content = json.loads(
                json.dumps(editable.json()["data"]["current_draft"]["content"])
            )
            edited_content["lesson_units"][0]["title"] = "1-5的认识 (教师修订)"
            saved = await client.put(
                f"/api/v2/artifacts/{artifact_id}/drafts/main",
                headers={
                    "Idempotency-Key": "r1-division-save-001",
                    "If-Match": editable.headers["ETag"],
                },
                json={"content": edited_content},
            )
            assert saved.status_code == 200, saved.text
            submitted = await client.post(
                f"/api/v2/artifacts/{artifact_id}/versions",
                headers={
                    "Idempotency-Key": "r1-division-submit-001",
                    "If-Match": saved.headers["ETag"],
                },
                json={"draft_branch": "main"},
            )
            assert submitted.status_code == 201, submitted.text
            submitted_version_id = UUID(submitted.json()["data"]["id"])

            quality = await client.post(
                f"/api/v2/projects/{project_id}/lesson-division/artifact-versions/"
                f"{submitted_version_id}/quality-validations",
                headers={"Idempotency-Key": "r1-division-quality-001"},
            )
            assert quality.status_code == 202, quality.text
            quality_node_id = UUID(quality.json()["data"]["node_run_id"])
            quality_result = execute_artifact_quality_node(
                postgres_database_url,
                quality_node_id,
                runtime_quality_validator_registry(),
            )
            assert quality_result is not None
            with factory() as session:
                quality_report = session.get(ArtifactQualityReport, quality_result.report_id)
                assert quality_report is not None
                findings = quality_report.findings_json
            assert quality_result.conclusion == "passed", findings
            quality_status = await client.get(
                f"/api/v2/projects/{project_id}/lesson-division/artifact"
            )
            assert quality_status.status_code == 200, quality_status.text
            assert quality_status.json()["data"]["quality_report"]["artifact_version_id"] == str(
                submitted_version_id
            )
            assert quality_status.json()["data"]["quality_report"]["conclusion"] == "passed"

            approved = await client.post(
                f"/api/v2/artifact-versions/{submitted_version_id}/approvals",
                headers={"Idempotency-Key": "r1-division-approve-001"},
                json={"action": "approve", "comment": "课时划分确认"},
            )
            assert approved.status_code == 201, approved.text
            assert approved.json()["data"]["artifact_version_id"] == str(submitted_version_id)

            refreshed = await client.get(f"/api/v2/projects/{project_id}/lesson-division/artifact")
            assert refreshed.status_code == 200, refreshed.text
            assert refreshed.json()["data"]["artifact"]["current_approved_version"]["id"] == str(
                submitted_version_id
            )
            assert refreshed.json()["data"]["latest_approval"]["artifact_version_id"] == str(
                submitted_version_id
            )
            lessons = await client.get(f"/api/v2/projects/{project_id}/lessons")
            assert lessons.status_code == 200, lessons.text
            assert [item["title"] for item in lessons.json()["data"]["items"]] == [
                "1-5的认识 (教师修订)"
            ]

            revised_scope = await client.post(
                f"/api/v2/projects/{project_id}/material-scope/versions",
                headers={"Idempotency-Key": "r1-division-scope-revision-001"},
                json={
                    "source_material_id": str(material_id),
                    "material_parse_version_id": str(parse_id),
                    "page_start": 1,
                    "page_end": 2,
                },
            )
            assert revised_scope.status_code == 201, revised_scope.text
            revised_scope_version_id = UUID(
                revised_scope.json()["data"]["current_submitted_version"]["id"]
            )
            revised_approval = await client.post(
                f"/api/v2/artifact-versions/{revised_scope_version_id}/approvals",
                headers={"Idempotency-Key": "r1-division-scope-revision-approve-001"},
                json={"action": "approve", "comment": "范围修订确认"},
            )
            assert revised_approval.status_code == 201, revised_approval.text
            stale_division = await client.get(
                f"/api/v2/projects/{project_id}/lesson-division/artifact"
            )
            assert stale_division.status_code == 200, stale_division.text
            assert stale_division.json()["data"]["artifact"]["status"] == "stale"

            revised_prepare = await client.post(
                f"/api/v2/projects/{project_id}/lesson-division/node-runs",
                headers={"Idempotency-Key": "r1-division-revision-prepare-001"},
                json={"material_scope_artifact_version_id": str(revised_scope_version_id)},
            )
            assert revised_prepare.status_code == 200, revised_prepare.text
            assert revised_prepare.json()["data"]["id"] != str(node_run_id)
            revised_start = await client.post(
                f"/api/v2/node-runs/{revised_prepare.json()['data']['id']}/start",
                headers={"Idempotency-Key": "r1-division-revision-start-001"},
                json={},
            )
            assert revised_start.status_code == 202, revised_start.text
            revision_jobs = await client.get(
                f"/api/v2/projects/{project_id}/lesson-division/generation-jobs"
            )
            assert revision_jobs.status_code == 200, revision_jobs.text
            assert len(revision_jobs.json()["data"]["items"]) == 2
    finally:
        app.state.database_engine.dispose()


async def test_r1_material_and_division_endpoints_reject_cross_tenant_access(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=postgres_database_url,
        session_access_code=None,
        session_allowed_origins=[],
        session_csrf_secret=None,
        session_teacher_principal_id=None,
    )
    app = create_app(settings=settings, object_storage=FakeObjectStorage())
    owner = configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_id, material_id, parse_id = await _project_with_material(
                client,
                app,
                owner,
                idempotency_key="r1-division-tenant-owner-project",
                title="租户隔离课时",
            )
            scope = await client.post(
                f"/api/v2/projects/{project_id}/material-scope/versions",
                headers={"Idempotency-Key": "r1-division-tenant-owner-scope"},
                json={
                    "source_material_id": str(material_id),
                    "material_parse_version_id": str(parse_id),
                    "page_start": 2,
                    "page_end": 2,
                },
            )
            assert scope.status_code == 201, scope.text
            scope_version_id = UUID(scope.json()["data"]["current_submitted_version"]["id"])
            approval = await client.post(
                f"/api/v2/artifact-versions/{scope_version_id}/approvals",
                headers={"Idempotency-Key": "r1-division-tenant-owner-approval"},
                json={"action": "approve"},
            )
            assert approval.status_code == 201, approval.text
            prepared = await client.post(
                f"/api/v2/projects/{project_id}/lesson-division/node-runs",
                headers={"Idempotency-Key": "r1-division-tenant-owner-prepare"},
                json={"material_scope_artifact_version_id": str(scope_version_id)},
            )
            assert prepared.status_code == 200, prepared.text
            started = await client.post(
                f"/api/v2/node-runs/{prepared.json()['data']['id']}/start",
                headers={"Idempotency-Key": "r1-division-tenant-owner-start"},
                json={},
            )
            assert started.status_code == 202, started.text

            factory = build_session_factory(app.state.database_engine)
            before = _r1_row_counts(factory)
            outsider = _seed_foreign_actor(factory)
            override_test_identity(app, outsider)
            for path in (
                f"/api/v2/projects/{project_id}/materials",
                f"/api/v2/projects/{project_id}/material-scope/artifact",
                f"/api/v2/projects/{project_id}/lesson-division/generation-jobs",
                f"/api/v2/projects/{project_id}/lesson-division/artifact",
            ):
                response = await client.get(path)
                assert response.status_code == 404, (path, response.text)
            foreign_scope = await client.post(
                f"/api/v2/projects/{project_id}/material-scope/versions",
                headers={"Idempotency-Key": "r1-division-tenant-foreign-scope"},
                json={
                    "source_material_id": str(material_id),
                    "material_parse_version_id": str(parse_id),
                    "page_start": 2,
                    "page_end": 2,
                },
            )
            assert foreign_scope.status_code == 404, foreign_scope.text
            foreign_prepare = await client.post(
                f"/api/v2/projects/{project_id}/lesson-division/node-runs",
                headers={"Idempotency-Key": "r1-division-tenant-foreign-prepare"},
                json={"material_scope_artifact_version_id": str(scope_version_id)},
            )
            assert foreign_prepare.status_code == 404, foreign_prepare.text
            assert _r1_row_counts(factory) == before
    finally:
        app.state.database_engine.dispose()


async def _project_with_material(
    client: httpx.AsyncClient,
    app,
    actor,
    *,
    idempotency_key: str,
    title: str,
) -> tuple[UUID, UUID, UUID]:
    factory = build_session_factory(app.state.database_engine)
    with factory() as session, session.begin():
        published = ContentReleasePublisher(session).publish(
            load_builtin_courseware_release(ROOT),
            published_by=actor.principal_id,
        )
        content_release_id = published.content_release_id
        workflow_definition_version_id = published.workflow_definition_version_id
    response = await client.post(
        "/api/v2/projects",
        headers={"Idempotency-Key": idempotency_key},
        json={"title": title, "knowledge_point": title},
    )
    assert response.status_code == 201, response.text
    project_id = UUID(response.json()["data"]["id"])
    with factory() as session, session.begin():
        project = session.get(Project, project_id)
        assert project is not None
        assert project.content_release_id == content_release_id
        assert project.workflow_definition_version_id == workflow_definition_version_id
        material_id, parse_id = _seed_material_parse(
            session,
            project_id=project_id,
            organization_id=actor.organization_id,
            principal_id=actor.principal_id,
        )
    return project_id, material_id, parse_id


def _seed_foreign_actor(factory: sessionmaker[Session]):
    organization_id = new_uuid7()
    with factory() as session, session.begin():
        session.add(
            Organization(
                id=organization_id,
                slug=f"r1-division-{organization_id.hex[:12]}",
                name="R1 division foreign tenant",
                status="active",
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        return seed_test_actor(
            session,
            organization_id=organization_id,
            user_id=new_uuid7(),
            principal_id=new_uuid7(),
            member_id=new_uuid7(),
            email=f"r1-division-{organization_id.hex[:12]}@example.test",
            display_name="R1 division foreign teacher",
        )


def _r1_row_counts(factory: sessionmaker[Session]) -> tuple[int, int, int]:
    with factory() as session:
        return (
            session.scalar(select(func.count()).select_from(ArtifactVersion)) or 0,
            session.scalar(select(func.count()).select_from(GenerationJob)) or 0,
            session.scalar(select(func.count()).select_from(LessonUnit)) or 0,
        )
