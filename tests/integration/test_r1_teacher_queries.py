from __future__ import annotations

from uuid import UUID

import httpx

from apps.api.database import build_session_factory
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.main import create_app
from apps.api.settings import Settings
from apps.api.uploads.models import SourceMaterial
from tests.conftest import run_migration
from tests.contract.test_stage0_resources import assert_contract_response
from tests.fakes.content_runtime import ensure_test_authoring_definition
from tests.fakes.identity import configure_test_identity
from tests.fakes.object_storage import FakeObjectStorage


async def test_project_material_artifact_and_job_queries_restore_persisted_facts(
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
            project_response = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "r1-query-project-001"},
                json={"title": "认识1到5", "knowledge_point": "认识1到5"},
            )
            assert project_response.status_code == 201
            project_id = UUID(project_response.json()["data"]["id"])

            material_ids: list[UUID] = []
            for index in range(2):
                upload = await client.post(
                    f"/api/v2/projects/{project_id}/materials/uploads",
                    headers={"Idempotency-Key": f"r1-query-upload-{index:03d}"},
                    json={
                        "filename": f"lesson-{index}.pdf",
                        "media_type": "application/pdf",
                        "size_bytes": index + 1,
                        "sha256": f"{index + 1:x}" * 64,
                    },
                )
                assert upload.status_code == 201
                material_ids.append(UUID(upload.json()["data"]["material_id"]))

            factory = build_session_factory(app.state.database_engine)
            with factory() as session, session.begin():
                definition_id = ensure_test_authoring_definition(session, project_id)

            artifact_ids: list[UUID] = []
            for index, artifact_type in enumerate(("material_scope", "lesson_division")):
                created = await client.post(
                    f"/api/v2/projects/{project_id}/artifacts",
                    headers={"Idempotency-Key": f"r1-query-artifact-{index:03d}"},
                    json={
                        "artifact_key": f"r1-query-{artifact_type}",
                        "artifact_type": artifact_type,
                        "branch_key": "project",
                        "content_definition_version_id": str(definition_id),
                        "content": {"title": artifact_type},
                    },
                )
                assert created.status_code == 201
                artifact_ids.append(UUID(created.json()["data"]["id"]))

            with factory() as session, session.begin():
                material = session.get(SourceMaterial, material_ids[0])
                assert material is not None
                job_id = new_uuid7()
                session.add(
                    GenerationJob(
                        id=job_id,
                        organization_id=actor.organization_id,
                        project_id=project_id,
                        source_material_id=material.id,
                        job_type="material.parse",
                        status="queued",
                        progress_percent=0,
                        priority=100,
                        created_by=actor.principal_id,
                        updated_by=actor.principal_id,
                    )
                )

            materials = await client.get(f"/api/v2/projects/{project_id}/materials?page[limit]=1")
            assert materials.status_code == 200, materials.text
            assert_contract_response(materials, operation_id="listProjectMaterials", status="200")
            assert len(materials.json()["data"]["items"]) == 1
            assert materials.json()["data"]["items"][0]["id"] == str(material_ids[1])
            assert materials.json()["meta"]["next_cursor"] is not None
            older_materials = await client.get(
                f"/api/v2/projects/{project_id}/materials",
                params={
                    "page[cursor]": materials.json()["meta"]["next_cursor"],
                    "page[limit]": 1,
                },
            )
            assert [item["id"] for item in older_materials.json()["data"]["items"]] == [
                str(material_ids[0])
            ]

            artifacts = await client.get(
                f"/api/v2/projects/{project_id}/artifacts",
                params={"artifact_type": "lesson_division", "page[limit]": 10},
            )
            assert artifacts.status_code == 200, artifacts.text
            assert_contract_response(artifacts, operation_id="listProjectArtifacts", status="200")
            assert [item["artifact_type"] for item in artifacts.json()["data"]["items"]] == [
                "lesson_division"
            ]
            assert artifacts.json()["data"]["items"][0]["id"] == str(artifact_ids[1])

            unrelated_lesson = new_uuid7()
            lesson_artifacts = await client.get(
                f"/api/v2/projects/{project_id}/artifacts",
                params={"lesson_id": str(unrelated_lesson)},
            )
            assert lesson_artifacts.status_code == 200
            assert lesson_artifacts.json()["data"]["items"] == []

            jobs = await client.get(f"/api/v2/projects/{project_id}/generation-jobs?page[limit]=10")
            assert jobs.status_code == 200, jobs.text
            assert_contract_response(jobs, operation_id="listProjectGenerationJobs", status="200")
            assert jobs.json()["data"]["items"][0]["project_id"] == str(project_id)
            assert jobs.json()["data"]["items"][0]["id"] == str(job_id)

            lesson_jobs = await client.get(
                f"/api/v2/projects/{project_id}/generation-jobs",
                params={"lesson_id": str(unrelated_lesson)},
            )
            assert lesson_jobs.status_code == 200
            assert lesson_jobs.json()["data"]["items"] == []

            for path in (
                f"/api/v2/projects/{project_id}/materials",
                f"/api/v2/projects/{project_id}/artifacts",
                f"/api/v2/projects/{project_id}/generation-jobs",
            ):
                invalid_cursor = await client.get(path, params={"page[cursor]": "invalid"})
                assert invalid_cursor.status_code == 422
                assert invalid_cursor.json()["error"]["code"] == "VALIDATION_FAILED"
    finally:
        app.state.database_engine.dispose()
