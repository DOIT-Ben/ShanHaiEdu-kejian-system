from __future__ import annotations

import json
from dataclasses import replace

import pytest
from sqlalchemy import func, select

from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.jobs.models import GenerationJob
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry, IdempotencyRecord
from apps.api.uploads.confirmation_service import UploadConfirmationService
from apps.api.uploads.models import SourceMaterial, UploadSession
from apps.api.uploads.schemas import ConfirmUploadRequest, CreateUploadSessionRequest
from apps.api.uploads.session_service import UploadSessionService
from apps.api.uploads.storage import ObjectMetadata, ObjectStorageError
from tests.fakes.identity import seed_test_actor
from tests.fakes.object_storage import FakeObjectStorage

SHA256 = "a" * 64


def test_upload_session_replay_resigns_without_persisting_the_presigned_url(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )
        service = UploadSessionService(
            session=session,
            storage=storage,
            actor=actor,
            bucket="shanhaiedu",
            ttl_seconds=900,
            max_size_bytes=10_000,
        )
        payload = CreateUploadSessionRequest(
            filename="lesson.pdf",
            media_type="application/pdf",
            size_bytes=4,
            sha256=SHA256,
        )

        first = service.create_session(
            project.id,
            payload,
            idempotency_key="create-upload-private-url",
            request_id="req-create-upload-private-url",
        )
        replay = service.create_session(
            project.id,
            payload,
            idempotency_key="create-upload-private-url",
            request_id="req-replay-upload-private-url",
        )

        record = session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == "material_uploads.create",
                IdempotencyRecord.idempotency_key == "create-upload-private-url",
            )
        )
        assert record is not None
        persisted = json.dumps(record.response_body_json)
        assert "upload_url" not in persisted
        assert "signature" not in persisted
        assert first.upload_session_id == replay.upload_session_id
        assert first.material_id == replay.material_id
        assert len(storage.presigned_requests) == 2
        assert session.scalar(select(func.count()).select_from(UploadSession)) == 1
        assert session.scalar(select(func.count()).select_from(SourceMaterial)) == 1


def test_upload_confirmation_validates_object_and_commits_atomically(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(
                    title="Fractions",
                    knowledge_point="Understanding one half",
                )
            )
        session_service = UploadSessionService(
            session=session,
            storage=storage,
            actor=actor,
            bucket="shanhaiedu",
            ttl_seconds=900,
            max_size_bytes=10_000,
        )
        upload = session_service.create_session(
            project.id,
            CreateUploadSessionRequest(
                filename="lesson.pdf",
                media_type="application/pdf",
                size_bytes=4,
                sha256=SHA256,
            ),
            idempotency_key="create-upload-session",
            request_id="req-create-upload",
        )
        assert storage.last_presigned is not None
        expected = ObjectMetadata(
            bucket=storage.last_presigned.bucket,
            key=storage.last_presigned.key,
            etag="etag-1",
            size_bytes=4,
            media_type="application/pdf",
            sha256=SHA256,
        )
        confirm = ConfirmUploadRequest(
            upload_session_id=upload.upload_session_id,
            etag='"etag-1"',
            size_bytes=4,
            sha256=SHA256,
        )
        confirmation_service = UploadConfirmationService(
            session=session,
            storage=storage,
            actor=actor,
        )

        with pytest.raises(ApiError, match="UPLOAD_REJECTED"):
            confirmation_service.confirm(
                project_id=project.id,
                material_id=upload.material_id,
                idempotency_key="confirm-size-mismatch",
                payload=confirm.model_copy(update={"size_bytes": 5}),
                request_id="req-size-mismatch",
                idempotency_ttl_seconds=900,
            )

        mismatches = (
            replace(expected, key="wrong/object-key"),
            replace(expected, etag="wrong-etag"),
            replace(expected, size_bytes=5),
            replace(expected, media_type="image/png"),
            replace(expected, sha256="b" * 64),
        )
        for metadata in mismatches:
            storage.put_at(bucket=expected.bucket, key=expected.key, metadata=metadata)
            with pytest.raises(ApiError, match="UPLOAD_REJECTED"):
                confirmation_service.confirm(
                    project_id=project.id,
                    material_id=upload.material_id,
                    idempotency_key="confirm-object-mismatch",
                    payload=confirm,
                    request_id="req-object-mismatch",
                    idempotency_ttl_seconds=900,
                )

        storage.put(expected)
        accepted = confirmation_service.confirm(
            project_id=project.id,
            material_id=upload.material_id,
            idempotency_key="confirm-success",
            payload=confirm,
            request_id="req-confirm-success",
            idempotency_ttl_seconds=900,
        )
        replayed = confirmation_service.confirm(
            project_id=project.id,
            material_id=upload.material_id,
            idempotency_key="confirm-success",
            payload=confirm,
            request_id="req-confirm-replay",
            idempotency_ttl_seconds=900,
        )

        assert accepted.status == "queued"
        assert replayed.job_id == accepted.job_id
        assert session.scalar(select(func.count()).select_from(FileAsset)) == 1
        assert session.scalar(select(func.count()).select_from(FileAssetVersion)) == 1
        assert session.scalar(select(func.count()).select_from(GenerationJob)) == 1
        version = session.scalar(select(FileAssetVersion))
        assert version is not None
        assert version.storage_key != expected.key
        with pytest.raises(ObjectStorageError):
            storage.stat(bucket=expected.bucket, key=expected.key)
        material = session.get(SourceMaterial, upload.material_id)
        persisted_upload = session.get(UploadSession, upload.upload_session_id)
        assert material is not None and material.upload_status == "confirmed"
        assert material.file_asset_id is not None
        assert persisted_upload is not None and persisted_upload.status == "confirmed"
        event = session.scalar(
            select(EventStreamEntry).where(
                EventStreamEntry.event_type == "material.upload.confirmed"
            )
        )
        assert event is not None
        assert event.summary_json["payload"] == {
            "status": "confirmed",
            "file_asset_id": str(material.file_asset_id),
            "file_asset_version_id": str(version.id),
        }


def test_same_hash_in_different_projects_keeps_distinct_stable_asset_identities(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            projects = [
                ProjectRepository(session, actor).create(
                    CreateProjectRequest(title=title, knowledge_point="One half")
                )
                for title in ("Project A", "Project B")
            ]

        material_ids = []
        for index, project in enumerate(projects):
            upload = UploadSessionService(
                session=session,
                storage=storage,
                actor=actor,
                bucket="shanhaiedu",
                ttl_seconds=900,
                max_size_bytes=10_000,
            ).create_session(
                project.id,
                CreateUploadSessionRequest(
                    filename="lesson.pdf",
                    media_type="application/pdf",
                    size_bytes=4,
                    sha256=SHA256,
                ),
                idempotency_key=f"same-hash-upload-{index:03d}",
                request_id=f"req-same-hash-upload-{index:03d}",
            )
            assert storage.last_presigned is not None
            storage.put(
                ObjectMetadata(
                    bucket=storage.last_presigned.bucket,
                    key=storage.last_presigned.key,
                    etag=f"etag-{index}",
                    size_bytes=4,
                    media_type="application/pdf",
                    sha256=SHA256,
                )
            )
            UploadConfirmationService(
                session=session,
                storage=storage,
                actor=actor,
            ).confirm(
                project_id=project.id,
                material_id=upload.material_id,
                idempotency_key=f"same-hash-confirm-{index:03d}",
                payload=ConfirmUploadRequest(
                    upload_session_id=upload.upload_session_id,
                    etag=f"etag-{index}",
                    size_bytes=4,
                    sha256=SHA256,
                ),
                request_id=f"req-same-hash-confirm-{index:03d}",
                idempotency_ttl_seconds=900,
            )
            material_ids.append(upload.material_id)

        materials = list(
            session.scalars(select(SourceMaterial).where(SourceMaterial.id.in_(material_ids)))
        )
        assert len(materials) == 2
        assert len({material.file_asset_id for material in materials}) == 2
        assert session.scalar(select(func.count()).select_from(FileAsset)) == 2
        assert session.scalar(select(func.count()).select_from(FileAssetVersion)) == 2
