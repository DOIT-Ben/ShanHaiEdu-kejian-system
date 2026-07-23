from __future__ import annotations

import httpx

from apps.api.main import create_app
from apps.api.settings import Settings
from apps.api.uploads.storage import ObjectMetadata
from tests.conftest import run_migration
from tests.contract.test_stage0_contracts import (
    load_openapi,
    operations_by_id,
    response_schema,
    validate,
)
from tests.fakes.identity import configure_test_identity
from tests.fakes.object_storage import FakeObjectStorage

SHA256 = "a" * 64


def assert_contract_response(
    response: httpx.Response,
    *,
    operation_id: str,
    status: str,
) -> None:
    openapi = load_openapi()
    operation = operations_by_id(openapi)[operation_id]
    schema = response_schema(openapi, operation, status, "application/json")
    validate(response.json(), schema)


async def test_project_upload_and_job_api_matches_stage0_contract(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    storage = FakeObjectStorage()
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=postgres_database_url,
    )
    app = create_app(settings=settings, object_storage=storage)
    configure_test_identity(app)
    operation_ids = [
        operation["operationId"]
        for path in app.openapi()["paths"].values()
        for operation in path.values()
    ]
    assert len(operation_ids) == len(set(operation_ids))
    assert {
        "createProject",
        "listProjects",
        "getProject",
        "createMaterialUploadSession",
        "confirmMaterialUpload",
        "listProjectMaterials",
        "getGenerationJob",
        "cancelGenerationJob",
        "streamGenerationJobEvents",
        "streamProjectEvents",
        "getSourceMaterialFileAsset",
        "listMaterialParseVersions",
    }.issubset(operation_ids)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_response = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "create-project-001"},
                json={
                    "title": "Fractions",
                    "knowledge_point": "Understanding one half",
                    "grade": "3",
                    "textbook_edition": "renjiao",
                },
            )
            assert project_response.status_code == 201
            assert_contract_response(project_response, operation_id="createProject", status="201")
            project_id = project_response.json()["data"]["id"]

            list_response = await client.get("/api/v2/projects?page[limit]=10")
            assert list_response.status_code == 200
            assert_contract_response(list_response, operation_id="listProjects", status="200")

            detail_response = await client.get(f"/api/v2/projects/{project_id}")
            assert detail_response.status_code == 200
            assert detail_response.headers["ETag"] == 'W/"1-1"'
            assert_contract_response(detail_response, operation_id="getProject", status="200")

            upload_response = await client.post(
                f"/api/v2/projects/{project_id}/materials/uploads",
                headers={"Idempotency-Key": "create-upload-001"},
                json={
                    "filename": "lesson.pdf",
                    "media_type": "application/pdf",
                    "size_bytes": 4,
                    "sha256": SHA256,
                },
            )
            assert upload_response.status_code == 201
            assert_contract_response(
                upload_response,
                operation_id="createMaterialUploadSession",
                status="201",
            )
            upload = upload_response.json()["data"]
            assert storage.last_presigned is not None
            storage.put(
                ObjectMetadata(
                    bucket=storage.last_presigned.bucket,
                    key=storage.last_presigned.key,
                    etag="etag-1",
                    size_bytes=4,
                    media_type="application/pdf",
                    sha256=SHA256,
                )
            )

            confirm_response = await client.post(
                f"/api/v2/projects/{project_id}/materials/{upload['material_id']}/confirm",
                headers={"Idempotency-Key": "confirm-upload-001"},
                json={
                    "upload_session_id": upload["upload_session_id"],
                    "etag": "etag-1",
                    "size_bytes": 4,
                    "sha256": SHA256,
                },
            )
            assert confirm_response.status_code == 202
            assert_contract_response(
                confirm_response,
                operation_id="confirmMaterialUpload",
                status="202",
            )
            materials_response = await client.get(
                f"/api/v2/projects/{project_id}/materials"
            )
            assert materials_response.status_code == 200
            assert_contract_response(
                materials_response,
                operation_id="listProjectMaterials",
                status="200",
            )
            assert materials_response.json()["data"]["items"] == [
                {
                    "id": upload["material_id"],
                    "original_filename": "lesson.pdf",
                    "mime_type": "application/pdf",
                    "upload_status": "confirmed",
                    "confirmed_at": materials_response.json()["data"]["items"][0][
                        "confirmed_at"
                    ],
                }
            ]
            job_id = confirm_response.json()["data"]["job_id"]

            job_response = await client.get(f"/api/v2/generation-jobs/{job_id}")
            assert job_response.status_code == 200
            assert_contract_response(job_response, operation_id="getGenerationJob", status="200")
    finally:
        app.state.database_engine.dispose()
