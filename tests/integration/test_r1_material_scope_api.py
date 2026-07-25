from __future__ import annotations

from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import func, select

from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.assets.models import FileAsset, FileAssetVersion, MaterialParseVersion
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_session_factory, utc_now
from apps.api.ids import new_uuid7
from apps.api.main import create_app
from apps.api.projects.models import Project
from apps.api.settings import Settings
from apps.api.uploads.models import SourceMaterial
from tests.conftest import run_migration
from tests.fakes.identity import configure_test_identity
from tests.fakes.object_storage import FakeObjectStorage

ROOT = Path(__file__).resolve().parents[2]


async def test_material_scope_command_appends_exact_submitted_versions(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
            session_access_code=None,
            session_allowed_origins=[],
            session_csrf_secret=None,
            session_teacher_principal_id=None,
        ),
        object_storage=FakeObjectStorage(),
    )
    actor = configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_response = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "r1-scope-project-001"},
                json={"title": "认识1到5", "knowledge_point": "认识1到5"},
            )
            assert project_response.status_code == 201
            project_id = UUID(project_response.json()["data"]["id"])

            factory = build_session_factory(app.state.database_engine)
            with factory() as session, session.begin():
                published = ContentReleasePublisher(session).publish(
                    load_builtin_courseware_release(ROOT),
                    published_by=actor.principal_id,
                )
                project = session.get(Project, project_id)
                assert project is not None
                project.content_release_id = published.content_release_id
                project.workflow_definition_version_id = published.workflow_definition_version_id
                material_id, parse_id = _seed_material_parse(
                    session,
                    project_id=project_id,
                    organization_id=actor.organization_id,
                    principal_id=actor.principal_id,
                )
                textbook = session.get(SourceMaterial, material_id)
                assert textbook is not None
                session.add(
                    SourceMaterial(
                        id=new_uuid7(),
                        organization_id=actor.organization_id,
                        project_id=project_id,
                        material_kind="supplement",
                        file_asset_id=textbook.file_asset_id,
                        original_filename="teacher-notes.pdf",
                        mime_type="application/pdf",
                        upload_status="confirmed",
                        confirmed_at=utc_now(),
                        confirmed_by=actor.principal_id,
                        created_by=actor.principal_id,
                        updated_by=actor.principal_id,
                    )
                )

            materials = await client.get(f"/api/v2/projects/{project_id}/materials")
            assert materials.status_code == 200, materials.text
            assert [item["id"] for item in materials.json()["data"]["items"]] == [str(material_id)]
            pages = await client.get(
                f"/api/v2/projects/{project_id}/materials/{material_id}/"
                f"parse-versions/{parse_id}/pages"
            )
            assert pages.status_code == 200, pages.text
            assert pages.json()["data"]["items"] == [
                {
                    "page_number": 1,
                    "text_preview": "",
                    "text_block_count": 0,
                    "image_count": 0,
                },
                {
                    "page_number": 2,
                    "text_preview": "page 2",
                    "text_block_count": 1,
                    "image_count": 1,
                },
                {
                    "page_number": 3,
                    "text_preview": "page 3",
                    "text_block_count": 1,
                    "image_count": 0,
                },
            ]

            payload = {
                "source_material_id": str(material_id),
                "material_parse_version_id": str(parse_id),
                "page_start": 2,
                "page_end": 2,
            }
            created = await client.post(
                f"/api/v2/projects/{project_id}/material-scope/versions",
                headers={"Idempotency-Key": "r1-scope-version-001"},
                json=payload,
            )
            assert created.status_code == 201, created.text
            created_data = created.json()["data"]
            first_version = created_data["current_submitted_version"]
            assert created_data["artifact_key"] == "material-scope"
            assert created_data["artifact_type"] == "material_scope"
            assert created_data["status"] == "in_review"
            assert first_version["version_no"] == 1
            assert first_version["content"] == {
                **payload,
                "knowledge_point": "认识1到5",
                "knowledge_boundary": {
                    "allowed": ["认识1到5"],
                    "forbidden": ["超出认识1到5及所选教材页段的内容"],
                },
                "approved_evidence_keys": ["p2-image-1", "p2-text-1"],
                "duration_minutes": 40,
                "lesson_count_mode": "auto",
                "lesson_type_preferences": [],
                "special_requirements": "",
            }

            replay = await client.post(
                f"/api/v2/projects/{project_id}/material-scope/versions",
                headers={"Idempotency-Key": "r1-scope-version-001"},
                json=payload,
            )
            assert replay.status_code == 201
            assert replay.json()["data"]["current_submitted_version"]["id"] == first_version["id"]

            conflict = await client.post(
                f"/api/v2/projects/{project_id}/material-scope/versions",
                headers={"Idempotency-Key": "r1-scope-version-001"},
                json={**payload, "page_start": 3, "page_end": 3},
            )
            assert conflict.status_code == 409
            assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

            approved = await client.post(
                f"/api/v2/artifact-versions/{first_version['id']}/approvals",
                headers={"Idempotency-Key": "r1-scope-approve-001"},
                json={"action": "approve", "comment": "范围已确认"},
            )
            assert approved.status_code == 201, approved.text

            revised = await client.post(
                f"/api/v2/projects/{project_id}/material-scope/versions",
                headers={"Idempotency-Key": "r1-scope-version-002"},
                json={**payload, "page_start": 3, "page_end": 3},
            )
            assert revised.status_code == 201, revised.text
            revised_data = revised.json()["data"]
            second_version = revised_data["current_submitted_version"]
            assert revised_data["id"] == created_data["id"]
            assert second_version["id"] != first_version["id"]
            assert second_version["version_no"] == 2
            assert second_version["content"]["approved_evidence_keys"] == ["p3-text-1"]

            with factory() as session:
                artifact_count = session.scalar(
                    select(func.count())
                    .select_from(Artifact)
                    .where(
                        Artifact.project_id == project_id,
                        Artifact.artifact_key == "material-scope",
                    )
                )
                version_count = session.scalar(
                    select(func.count())
                    .select_from(ArtifactVersion)
                    .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
                    .where(
                        Artifact.project_id == project_id,
                        Artifact.artifact_key == "material-scope",
                    )
                )
                assert artifact_count == 1
                assert version_count == 2
    finally:
        app.state.database_engine.dispose()


async def test_material_scope_command_rejects_invalid_source_range_and_evidence(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
            session_access_code=None,
            session_allowed_origins=[],
            session_csrf_secret=None,
            session_teacher_principal_id=None,
        ),
        object_storage=FakeObjectStorage(),
    )
    actor = configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_response = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "r1-scope-errors-project-001"},
                json={"title": "认识1到5", "knowledge_point": "认识1到5"},
            )
            project_id = UUID(project_response.json()["data"]["id"])
            factory = build_session_factory(app.state.database_engine)
            with factory() as session, session.begin():
                published = ContentReleasePublisher(session).publish(
                    load_builtin_courseware_release(ROOT),
                    published_by=actor.principal_id,
                )
                project = session.get(Project, project_id)
                assert project is not None
                project.content_release_id = published.content_release_id
                project.workflow_definition_version_id = published.workflow_definition_version_id
                material_id, parse_id = _seed_material_parse(
                    session,
                    project_id=project_id,
                    organization_id=actor.organization_id,
                    principal_id=actor.principal_id,
                )
                succeeded_parse = session.get(MaterialParseVersion, parse_id)
                assert succeeded_parse is not None
                pending_parse_id = new_uuid7()
                session.add(
                    MaterialParseVersion(
                        id=pending_parse_id,
                        organization_id=actor.organization_id,
                        source_material_id=material_id,
                        file_asset_version_id=succeeded_parse.file_asset_version_id,
                        generation_job_id=None,
                        version_no=2,
                        status="pending",
                        parser_name="r1-scope-fake",
                        parser_version="2",
                        content_json=None,
                        page_count=None,
                        text_checksum=None,
                        validation_report_json={},
                        error_code=None,
                        created_at=utc_now(),
                        started_at=None,
                        completed_at=None,
                        created_by=actor.principal_id,
                        updated_by=actor.principal_id,
                    )
                )

            base_payload = {
                "source_material_id": str(material_id),
                "material_parse_version_id": str(parse_id),
                "page_start": 2,
                "page_end": 2,
            }
            cases = (
                (
                    "r1-scope-errors-missing",
                    {**base_payload, "material_parse_version_id": str(new_uuid7())},
                    404,
                    "MATERIAL_SCOPE_SOURCE_NOT_FOUND",
                ),
                (
                    "r1-scope-errors-range",
                    {**base_payload, "page_start": 3, "page_end": 4},
                    422,
                    "INVALID_MATERIAL_SCOPE",
                ),
                (
                    "r1-scope-errors-evidence",
                    {**base_payload, "page_start": 1, "page_end": 1},
                    422,
                    "INVALID_MATERIAL_SCOPE",
                ),
            )
            for key, payload, expected_status, expected_code in cases:
                response = await client.post(
                    f"/api/v2/projects/{project_id}/material-scope/versions",
                    headers={"Idempotency-Key": key},
                    json=payload,
                )
                assert response.status_code == expected_status, response.text
                assert response.json()["error"]["code"] == expected_code

            pending = await client.post(
                f"/api/v2/projects/{project_id}/material-scope/versions",
                headers={"Idempotency-Key": "r1-scope-errors-pending"},
                json={**base_payload, "material_parse_version_id": str(pending_parse_id)},
            )
            assert pending.status_code == 409
            assert pending.json()["error"]["code"] == "MATERIAL_PARSE_NOT_READY"

            with factory() as session:
                artifact_count = session.scalar(
                    select(func.count())
                    .select_from(Artifact)
                    .where(Artifact.project_id == project_id)
                )
                assert artifact_count == 0
    finally:
        app.state.database_engine.dispose()


def _seed_material_parse(
    session,
    *,
    project_id: UUID,
    organization_id: UUID,
    principal_id: UUID,
) -> tuple[UUID, UUID]:
    asset = FileAsset(
        id=new_uuid7(),
        organization_id=organization_id,
        asset_key=f"r1-scope-material:{project_id}",
        asset_kind="source_material",
        current_version_id=None,
        status="active",
        retention_class="project",
        created_by=principal_id,
        updated_by=principal_id,
    )
    session.add(asset)
    session.flush()
    file_version = FileAssetVersion(
        id=new_uuid7(),
        organization_id=organization_id,
        file_asset_id=asset.id,
        version_no=1,
        storage_bucket="test-only",
        storage_key=f"r1-scope/{project_id}/material.pdf",
        mime_type="application/pdf",
        byte_size=3,
        sha256="a" * 64,
        etag="r1-scope",
        width=None,
        height=None,
        duration_ms=None,
        page_count=3,
        scan_status="clean",
        metadata_json={},
        derived_from_version_id=None,
        created_at=utc_now(),
        created_by=principal_id,
    )
    session.add(file_version)
    session.flush()
    asset.current_version_id = file_version.id
    material = SourceMaterial(
        id=new_uuid7(),
        organization_id=organization_id,
        project_id=project_id,
        material_kind="textbook",
        file_asset_id=asset.id,
        original_filename="material.pdf",
        mime_type="application/pdf",
        upload_status="confirmed",
        confirmed_at=utc_now(),
        confirmed_by=principal_id,
        created_by=principal_id,
        updated_by=principal_id,
    )
    session.add(material)
    session.flush()
    pages = [
        {
            "page_number": page_number,
            "text_blocks": (
                []
                if page_number == 1
                else [
                    {
                        "block_id": f"p{page_number}-text-1",
                        "text": f"page {page_number}",
                        "text_checksum": f"{page_number}" * 64,
                        "bbox": None,
                    }
                ]
            ),
            "image_references": (
                [
                    {
                        "image_id": "p2-image-1",
                        "object_name": "page-2-image.png",
                        "kind": "embedded",
                    }
                ]
                if page_number == 2
                else []
            ),
        }
        for page_number in range(1, 4)
    ]
    parse = MaterialParseVersion(
        id=new_uuid7(),
        organization_id=organization_id,
        source_material_id=material.id,
        file_asset_version_id=file_version.id,
        generation_job_id=None,
        version_no=1,
        status="succeeded",
        parser_name="r1-scope-fake",
        parser_version="1",
        content_json={
            "schema_version": "material-evidence-package.v1",
            "source": {
                "file_asset_version_id": str(file_version.id),
                "sha256": "a" * 64,
                "mime_type": "application/pdf",
                "byte_size": 3,
            },
            "parser": {"name": "r1-scope-fake", "version": "1"},
            "pages": pages,
            "material_evidence": [
                {
                    "evidence_key": "p2-image-1",
                    "supported_claim": "page 2 image evidence",
                },
                {
                    "evidence_key": "p2-text-1",
                    "supported_claim": "page 2 text evidence",
                },
                {
                    "evidence_key": "p3-text-1",
                    "supported_claim": "page 3 text evidence",
                },
            ],
        },
        page_count=3,
        text_checksum="b" * 64,
        validation_report_json={"valid": True},
        error_code=None,
        created_at=utc_now(),
        started_at=utc_now(),
        completed_at=utc_now(),
        created_by=principal_id,
        updated_by=principal_id,
    )
    session.add(parse)
    session.flush()
    return material.id, parse.id
