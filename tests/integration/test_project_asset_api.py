from __future__ import annotations

import json

import httpx

from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
)
from apps.api.assets.project_service import ProjectAssetService
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.ids import new_uuid7
from apps.api.main import create_app
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.settings import Settings
from tests.conftest import run_migration
from tests.contract.test_stage0_resources import assert_contract_response
from tests.fakes.identity import configure_test_identity


def seed_image_version(session, actor) -> FileAssetVersion:
    asset = FileAsset(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        asset_key=f"test:image:{new_uuid7()}",
        asset_kind="image",
        status="active",
        retention_class="project_asset",
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(asset)
    session.flush()
    version = FileAssetVersion(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        file_asset_id=asset.id,
        version_no=1,
        storage_bucket="private-bucket",
        storage_key=f"private/{asset.id}/image.png",
        mime_type="image/png",
        byte_size=4,
        sha256="b" * 64,
        etag=f"etag-{asset.id}",
        scan_status="clean",
        metadata_json={},
        created_at=utc_now(),
        created_by=actor.principal_id,
    )
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    return version


async def test_binding_api_is_idempotent_and_asset_package_hides_storage(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    settings = Settings(_env_file=None, environment="test", database_url=postgres_database_url)
    app = create_app(settings=settings)
    actor = configure_test_identity(app)
    factory = build_session_factory(build_engine(postgres_database_url))
    with factory() as session, session.begin():
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        first_version = seed_image_version(session, actor)
        second_version = seed_image_version(session, actor)
        service = ProjectAssetService(session, actor)
        slot = service.declare_slot(
            project.id,
            AssetSlotDeclaration(
                slot_key="project.image.selected",
                asset_type="image",
                cardinality=AssetCardinality.ONE,
                required=True,
                target_contract=AssetTargetContract(allowed_mime_types=("image/*",)),
            ),
            request_id="req-api-declare-one",
        )
        service.declare_slot(
            project.id,
            AssetSlotDeclaration(
                slot_key="project.image.candidates",
                asset_type="image",
                cardinality=AssetCardinality.MANY,
                target_contract=AssetTargetContract(allowed_mime_types=("image/*",)),
            ),
            request_id="req-api-declare-many",
        )

    transport = httpx.ASGITransport(app=app)
    payload = {
        "file_asset_version_id": str(first_version.id),
        "source_artifact_version_id": None,
        "replace_mode": "reject_if_occupied",
        "position": None,
    }
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                f"/api/v2/asset-slots/{slot.id}/bindings",
                headers={"Idempotency-Key": "asset-bind-001"},
                json=payload,
            )
            replay = await client.post(
                f"/api/v2/asset-slots/{slot.id}/bindings",
                headers={"Idempotency-Key": "asset-bind-001"},
                json=payload,
            )
            conflict = await client.post(
                f"/api/v2/asset-slots/{slot.id}/bindings",
                headers={"Idempotency-Key": "asset-bind-001"},
                json={**payload, "file_asset_version_id": str(second_version.id)},
            )
            first_page = await client.get(
                f"/api/v2/projects/{project.id}/asset-slots",
                params={"page[limit]": 1},
            )
            package = await client.get(
                f"/api/v2/projects/{project.id}/asset-package",
                params={"slot_key": "project.image.selected"},
            )
            binding_id = first.json()["data"]["id"]
            unbound = await client.post(
                f"/api/v2/asset-bindings/{binding_id}/unbind",
                headers={"Idempotency-Key": "asset-unbind-001"},
            )
            unbound_replay = await client.post(
                f"/api/v2/asset-bindings/{binding_id}/unbind",
                headers={"Idempotency-Key": "asset-unbind-001"},
            )
    finally:
        app.state.database_engine.dispose()

    assert first.status_code == 201
    assert_contract_response(first, operation_id="bindProjectAsset", status="201")
    assert replay.status_code == 201
    assert replay.json()["data"] == first.json()["data"]
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert first_page.status_code == 200
    assert_contract_response(first_page, operation_id="listProjectAssetSlots", status="200")
    assert len(first_page.json()["data"]["items"]) == 1
    assert first_page.json()["meta"]["next_cursor"] is not None
    assert package.status_code == 200
    assert_contract_response(package, operation_id="getProjectAssetPackage", status="200")
    assert package.json()["data"]["items"][0]["slot_key"] == "project.image.selected"
    rendered_package = json.dumps(package.json())
    assert "private-bucket" not in rendered_package
    assert "private/" not in rendered_package
    assert unbound.status_code == 200
    assert_contract_response(unbound, operation_id="unbindProjectAsset", status="200")
    assert unbound.json()["data"]["is_active"] is False
    assert unbound_replay.json()["data"] == unbound.json()["data"]
