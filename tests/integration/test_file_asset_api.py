from __future__ import annotations

from pathlib import Path
from uuid import UUID

import httpx

from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.service import MaterialParseService
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_session_factory
from apps.api.main import create_app
from apps.api.settings import Settings
from apps.api.uploads.models import SourceMaterial
from apps.api.uploads.storage import ObjectMetadata
from tests.conftest import run_migration
from tests.contract.test_stage0_resources import assert_contract_response
from tests.fakes.identity import configure_test_identity
from tests.fakes.object_storage import FakeObjectStorage

SHA256 = "d" * 64
ROOT = Path(__file__).resolve().parents[2]


async def test_material_file_asset_and_parse_version_summaries_are_tenant_safe_metadata(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    storage = FakeObjectStorage()
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
        ),
        object_storage=storage,
    )
    actor = configure_test_identity(app)
    factory = build_session_factory(app.state.database_engine)
    with factory() as session, session.begin():
        ContentReleasePublisher(session).publish(
            load_builtin_courseware_release(ROOT),
            published_by=actor.principal_id,
        )
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_response = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "asset-api-project-001"},
                json={"title": "Fractions", "knowledge_point": "One half"},
            )
            project_id = UUID(project_response.json()["data"]["id"])
            upload_response = await client.post(
                f"/api/v2/projects/{project_id}/materials/uploads",
                headers={"Idempotency-Key": "asset-api-upload-001"},
                json={
                    "filename": "lesson.pdf",
                    "media_type": "application/pdf",
                    "size_bytes": 4,
                    "sha256": SHA256,
                },
            )
            upload = upload_response.json()["data"]
            assert storage.last_presigned is not None
            storage.put(
                ObjectMetadata(
                    bucket=storage.last_presigned.bucket,
                    key=storage.last_presigned.key,
                    etag="asset-etag",
                    size_bytes=4,
                    media_type="application/pdf",
                    sha256=SHA256,
                )
            )
            confirmed = await client.post(
                f"/api/v2/projects/{project_id}/materials/{upload['material_id']}/confirm",
                headers={"Idempotency-Key": "asset-api-confirm-001"},
                json={
                    "upload_session_id": upload["upload_session_id"],
                    "etag": "asset-etag",
                    "size_bytes": 4,
                    "sha256": SHA256,
                },
            )
            assert confirmed.status_code == 202

            with factory() as session, session.begin():
                material = session.get(SourceMaterial, UUID(upload["material_id"]))
                assert material is not None and material.file_asset_id is not None
                asset = session.get(FileAsset, material.file_asset_id)
                assert asset is not None and asset.current_version_id is not None
                version = session.get(FileAssetVersion, asset.current_version_id)
                assert version is not None
                parse = MaterialParseService(session, actor).create(
                    material.id,
                    version.id,
                    parser_name="fake-pdf",
                    parser_version="1.0",
                )
                MaterialParseService(session, actor).start(parse.id)
                MaterialParseService(session, actor).complete(
                    parse.id,
                    content={
                        "pages": [
                            {
                                "page_number": 1,
                                "text_blocks": [
                                    {"block_id": "p1-text-1", "text": "one half"}
                                ],
                                "image_references": [],
                            }
                        ]
                    },
                    page_count=1,
                    text_checksum="e" * 64,
                    validation_report={"valid": True},
                )

            prepared_response = await client.post(
                f"/api/v2/projects/{project_id}/lesson-division-runs",
                headers={"Idempotency-Key": "asset-api-prepare-001"},
                json={
                    "material_id": str(material.id),
                    "material_parse_version_id": str(parse.id),
                    "page_start": 1,
                    "page_end": 1,
                    "duration_minutes": 40,
                    "requested_lesson_count": None,
                    "special_requirements": "Use the selected textbook page only.",
                },
            )
            assert prepared_response.status_code == 201, prepared_response.text
            assert_contract_response(
                prepared_response,
                operation_id="prepareLessonDivision",
                status="201",
            )
            prepared = prepared_response.json()["data"]
            assert prepared["material_scope_artifact_id"]
            assert prepared["material_scope_version_id"]
            assert prepared["generate_node_run_id"]
            assert prepared["validate_node_run_id"]
            assert prepared["gate_node_run_id"]

            asset_response = await client.get(
                f"/api/v2/projects/{project_id}/materials/{material.id}/file-asset"
            )
            parses_response = await client.get(
                f"/api/v2/projects/{project_id}/materials/{material.id}/parse-versions"
            )

        assert asset_response.status_code == 200, asset_response.text
        assert_contract_response(
            asset_response,
            operation_id="getSourceMaterialFileAsset",
            status="200",
        )
        assert asset_response.headers["ETag"] == 'W/"1"'
        asset_data = asset_response.json()["data"]
        assert asset_data["id"] == str(asset.id)
        assert asset_data["current_version"]["page_count"] == 1
        assert "storage_bucket" not in asset_data["current_version"]
        assert "storage_key" not in asset_data["current_version"]
        assert "etag" not in asset_data["current_version"]

        assert parses_response.status_code == 200, parses_response.text
        assert_contract_response(
            parses_response,
            operation_id="listMaterialParseVersions",
            status="200",
        )
        parse_items = parses_response.json()["data"]["items"]
        assert parse_items[0]["status"] == "succeeded"
        assert parse_items[0]["file_asset_version_id"] == str(version.id)
        assert "content_json" not in parse_items[0]
    finally:
        app.state.database_engine.dispose()
