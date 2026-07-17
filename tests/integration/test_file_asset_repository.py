from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from apps.api.assets.models import FileAsset, FileAssetVersion, MaterialParseVersion
from apps.api.assets.repository import FileAssetRepository
from apps.api.assets.service import MaterialParseService
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.context import system_actor
from apps.api.identity.models import SYSTEM_PRINCIPAL_ID
from apps.api.ids import new_uuid7
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.uploads.models import SourceMaterial
from tests.fakes.identity import seed_test_actor

SHA256 = "a" * 64


def seed_confirmed_material(session, actor):
    project = ProjectRepository(session, actor).create(
        CreateProjectRequest(title="Fractions", knowledge_point="One half")
    )
    asset = FileAsset(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        asset_key=f"material:{new_uuid7()}",
        asset_kind="source_material",
        status="active",
        retention_class="project_source",
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
        storage_bucket="shanhaiedu",
        storage_key=f"immutable/{asset.id}/source.pdf",
        mime_type="application/pdf",
        byte_size=4,
        sha256=SHA256,
        etag="etag-1",
        scan_status="pending",
        metadata_json={},
        created_at=utc_now(),
        created_by=actor.principal_id,
    )
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    material = SourceMaterial(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        project_id=project.id,
        material_kind="textbook",
        file_asset_id=asset.id,
        original_filename="lesson.pdf",
        mime_type="application/pdf",
        upload_status="confirmed",
        confirmed_at=utc_now(),
        confirmed_by=actor.principal_id,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(material)
    session.flush()
    return project, material, asset, version


def test_asset_repository_returns_stable_identity_and_current_version_with_tenant_scope(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project, material, asset, version = seed_confirmed_material(session, actor)

        record = FileAssetRepository(session, actor).get_for_material(project.id, material.id)
        assert record is not None
        assert record.asset.id == asset.id
        assert record.current_version.id == version.id
        assert (
            FileAssetRepository(
                session,
                replace(actor, organization_id=uuid4()),
            ).get_for_material(project.id, material.id)
            is None
        )


def test_parse_failure_retry_creates_new_version_and_success_is_terminal(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            _, material, _, version = seed_confirmed_material(session, actor)
            service = MaterialParseService(session, actor)
            first = service.create(
                material.id,
                version.id,
                parser_name="fake-pdf",
                parser_version="1.0",
            )
            service.start(first.id)
            service.fail(first.id, error_code="INVALID_PDF", validation_report={"valid": False})

        with session.begin():
            retry = MaterialParseService(session, actor).create(
                material.id,
                version.id,
                parser_name="fake-pdf",
                parser_version="1.0",
            )
            MaterialParseService(session, actor).start(retry.id)
            completed = MaterialParseService(session, actor).complete(
                retry.id,
                content={"pages": [{"page": 1, "text": "one half"}]},
                page_count=1,
                text_checksum="b" * 64,
                validation_report={"valid": True},
            )

        assert first.version_no == 1
        assert retry.version_no == 2
        assert completed.status == "succeeded"
        assert session.scalar(select(func.count()).select_from(MaterialParseVersion)) == 2
        assert session.get(FileAssetVersion, version.id).page_count == 1


def test_postgres_blocks_file_core_overwrite_and_terminal_parse_mutation(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            _, material, _, version = seed_confirmed_material(session, actor)
            service = MaterialParseService(session, actor)
            parse = service.create(
                material.id,
                version.id,
                parser_name="fake-pdf",
                parser_version="1.0",
            )
            service.start(parse.id)
            service.complete(
                parse.id,
                content={"pages": []},
                page_count=1,
                text_checksum="c" * 64,
                validation_report={"valid": True},
            )

        with pytest.raises(DBAPIError), session.begin_nested():
            persisted_version = session.get(FileAssetVersion, version.id)
            persisted_version.storage_key = "immutable/replaced.pdf"
            session.flush()

        with pytest.raises(DBAPIError), session.begin_nested():
            persisted_version = session.get(FileAssetVersion, version.id)
            persisted_version.page_count = 2
            session.flush()

        with pytest.raises(DBAPIError), session.begin_nested():
            persisted_parse = session.get(MaterialParseVersion, parse.id)
            persisted_parse.content_json = {"pages": [{"changed": True}]}
            session.flush()


def test_postgres_rejects_duplicate_storage_keys_and_negative_file_sizes(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            _, _, asset, version = seed_confirmed_material(session, actor)

        def candidate(*, storage_key: str, byte_size: int, version_no: int) -> FileAssetVersion:
            return FileAssetVersion(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                file_asset_id=asset.id,
                version_no=version_no,
                storage_bucket="shanhaiedu",
                storage_key=storage_key,
                mime_type="application/pdf",
                byte_size=byte_size,
                sha256="f" * 64,
                etag=f"etag-{version_no}",
                scan_status="pending",
                metadata_json={},
                created_at=utc_now(),
                created_by=actor.principal_id,
            )

        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                candidate(
                    storage_key=version.storage_key,
                    byte_size=4,
                    version_no=2,
                )
            )
            session.flush()

        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                candidate(
                    storage_key=f"immutable/{asset.id}/negative.pdf",
                    byte_size=-1,
                    version_no=3,
                )
            )
            session.flush()


def test_tenant_scoped_system_actor_can_start_worker_parse_version(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            owner = seed_test_actor(session)
            _, material, _, version = seed_confirmed_material(session, owner)

        with session.begin():
            created = MaterialParseService(session, owner).create(
                material.id,
                version.id,
                parser_name="fake-worker-pdf",
                parser_version="1.0",
            )

        with session.begin():
            started = MaterialParseService(
                session,
                system_actor(owner.organization_id),
            ).start(created.id)

        assert started.status == "running"
        assert started.updated_by == SYSTEM_PRINCIPAL_ID
