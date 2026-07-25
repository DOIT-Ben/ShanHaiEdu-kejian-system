from __future__ import annotations

from pathlib import Path
from uuid import UUID

import httpx

from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_session_factory
from apps.api.main import create_app
from apps.api.projects.models import Project
from apps.api.settings import Settings
from apps.api.workflows.artifact_input_selection import ArtifactInputSelectionReader
from tests.conftest import run_migration
from tests.fakes.identity import configure_test_identity
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_r1_material_scope_api import _seed_material_parse

ROOT = Path(__file__).resolve().parents[2]


async def test_lesson_division_prepare_start_and_refresh_are_exact(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
        ),
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
