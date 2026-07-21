from __future__ import annotations

from uuid import uuid4

from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.provider_media import SqlAlchemyProviderMediaAssetReader
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.ids import new_uuid7
from tests.fakes.identity import seed_test_actor


def test_asset_reader_returns_only_active_clean_same_tenant_image_versions(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        asset, clean = _image_asset(session, actor.organization_id, actor.principal_id)
        reader = SqlAlchemyProviderMediaAssetReader(session)

        found = reader.get_clean_image_version(
            organization_id=actor.organization_id,
            file_version_id=clean.id,
        )

        assert found is not None
        assert found.id == clean.id
        assert found.storage_key == clean.storage_key
        assert (
            reader.get_clean_image_version(
                organization_id=uuid4(),
                file_version_id=clean.id,
            )
            is None
        )

        asset.status = "rejected"
        assert (
            reader.get_clean_image_version(
                organization_id=actor.organization_id,
                file_version_id=clean.id,
            )
            is None
        )


def test_asset_reader_rejects_pending_scan_versions(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        _, pending = _image_asset(
            session,
            actor.organization_id,
            actor.principal_id,
            scan_status="pending",
        )

        assert (
            SqlAlchemyProviderMediaAssetReader(session).get_clean_image_version(
                organization_id=actor.organization_id,
                file_version_id=pending.id,
            )
            is None
        )


def _image_asset(session, organization_id, principal_id, *, scan_status: str = "clean"):
    asset = FileAsset(
        id=new_uuid7(),
        organization_id=organization_id,
        asset_key=f"image:{new_uuid7()}",
        asset_kind="image_reference",
        status="active",
        retention_class="project_media",
        created_by=principal_id,
        updated_by=principal_id,
    )
    session.add(asset)
    session.flush()
    version = FileAssetVersion(
        id=new_uuid7(),
        organization_id=organization_id,
        file_asset_id=asset.id,
        version_no=1,
        storage_bucket="shanhaiedu",
        storage_key=f"immutable/{asset.id}/reference.png",
        mime_type="image/png",
        byte_size=24,
        sha256="a" * 64,
        etag="etag-image-1",
        scan_status=scan_status,
        metadata_json={},
        created_at=utc_now(),
        created_by=principal_id,
    )
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    return asset, version
