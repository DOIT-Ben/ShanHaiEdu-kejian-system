"""Upload object verification and atomic material confirmation."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.models import SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.schemas import AcceptedJobData
from apps.api.uploads.models import FileAsset, FileAssetVersion, SourceMaterial, UploadSession
from apps.api.uploads.schemas import ConfirmUploadRequest
from apps.api.uploads.session_service import normalized_media_type
from apps.api.uploads.storage import ObjectMetadata, ObjectStorage, ObjectStorageError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UploadSnapshot:
    project_id: UUID
    material_id: UUID
    bucket: str
    key: str
    media_type: str
    size_bytes: int
    sha256: str
    status: str
    expires_at: datetime


def normalized_etag(value: str) -> str:
    return value.strip().strip('"')


class UploadConfirmationService:
    def __init__(self, *, session: Session, storage: ObjectStorage) -> None:
        self._session = session
        self._storage = storage

    def confirm(
        self,
        *,
        project_id: UUID,
        material_id: UUID,
        idempotency_key: str,
        payload: ConfirmUploadRequest,
    ) -> AcceptedJobData:
        snapshot = self._snapshot(project_id, material_id, payload.upload_session_id)
        self._validate_confirmation_payload(snapshot, payload)
        self._session.rollback()
        try:
            metadata = self._storage.stat(bucket=snapshot.bucket, key=snapshot.key)
        except ObjectStorageError as exc:
            raise self._upload_rejected("The uploaded object is unavailable.") from exc
        self._validate_object(snapshot, payload, metadata)
        asset_id, version_id, immutable = self._copy_to_immutable(snapshot)

        try:
            with self._session.begin():
                upload = self._find_upload(project_id, material_id, payload.upload_session_id)
                if upload is None or upload.status != "created" or upload.expires_at <= utc_now():
                    raise self._upload_rejected("The upload session is no longer confirmable.")
                material = self._session.get(SourceMaterial, material_id)
                if material is None or material.organization_id != SYSTEM_ORGANIZATION_ID:
                    raise self._upload_rejected("The upload material is unavailable.")
                job = self._persist_confirmation(
                    upload=upload,
                    material=material,
                    asset_id=asset_id,
                    version_id=version_id,
                    metadata=immutable,
                    idempotency_key=idempotency_key,
                    payload=payload,
                )
        except Exception:
            self._delete_best_effort(immutable.bucket, immutable.key, role="immutable_copy")
            raise
        self._delete_best_effort(snapshot.bucket, snapshot.key, role="temporary_upload")
        return AcceptedJobData(
            job_id=job.id,
            status="queued",
            events_url=f"/api/v2/generation-jobs/{job.id}/events/stream",
        )

    def _copy_to_immutable(self, snapshot: UploadSnapshot) -> tuple[UUID, UUID, ObjectMetadata]:
        asset_id = new_uuid7()
        version_id = new_uuid7()
        destination_key = (
            f"organizations/{SYSTEM_ORGANIZATION_ID}/file-assets/{asset_id}/"
            f"versions/{version_id}/source.pdf"
        )
        try:
            copied = self._storage.copy(
                source_bucket=snapshot.bucket,
                source_key=snapshot.key,
                destination_bucket=snapshot.bucket,
                destination_key=destination_key,
            )
        except ObjectStorageError as exc:
            raise self._upload_rejected("The uploaded object could not be finalized.") from exc
        if not (
            copied.bucket == snapshot.bucket
            and copied.key == destination_key
            and copied.size_bytes == snapshot.size_bytes
            and normalized_media_type(copied.media_type) == snapshot.media_type
            and copied.sha256 == snapshot.sha256
        ):
            self._delete_best_effort(copied.bucket, copied.key, role="invalid_copy")
            raise self._upload_rejected("The finalized object failed integrity validation.")
        return asset_id, version_id, copied

    def _snapshot(self, project_id: UUID, material_id: UUID, upload_id: UUID) -> UploadSnapshot:
        upload = self._find_upload(project_id, material_id, upload_id, lock=False)
        if upload is None:
            raise self._upload_rejected("The upload session was not found.")
        return UploadSnapshot(
            project_id=upload.project_id,
            material_id=upload.material_id,
            bucket=upload.storage_bucket,
            key=upload.storage_key,
            media_type=upload.expected_media_type,
            size_bytes=upload.expected_size_bytes,
            sha256=upload.expected_sha256,
            status=upload.status,
            expires_at=upload.expires_at,
        )

    def _find_upload(
        self,
        project_id: UUID,
        material_id: UUID,
        upload_id: UUID,
        *,
        lock: bool = True,
    ) -> UploadSession | None:
        statement = select(UploadSession).where(
            UploadSession.id == upload_id,
            UploadSession.project_id == project_id,
            UploadSession.material_id == material_id,
            UploadSession.organization_id == SYSTEM_ORGANIZATION_ID,
            UploadSession.deleted_at.is_(None),
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def _persist_confirmation(
        self,
        *,
        upload: UploadSession,
        material: SourceMaterial,
        asset_id: UUID,
        version_id: UUID,
        metadata: ObjectMetadata,
        idempotency_key: str,
        payload: ConfirmUploadRequest,
    ) -> GenerationJob:
        now = utc_now()
        asset = self._create_asset_version(material, asset_id, version_id, metadata, payload, now)
        self._mark_confirmed(upload, material, asset, now)
        job = self._create_job(upload, material, idempotency_key, payload)
        self._session.add(job)
        self._session.flush()
        return job

    def _create_asset_version(
        self,
        material: SourceMaterial,
        asset_id: UUID,
        version_id: UUID,
        metadata: ObjectMetadata,
        payload: ConfirmUploadRequest,
        created_at: datetime,
    ) -> FileAsset:
        asset = FileAsset(
            id=asset_id,
            organization_id=SYSTEM_ORGANIZATION_ID,
            asset_key=f"material:{material.id}",
            asset_kind="source_material",
            status="active",
            retention_class="project_source",
            created_by=SYSTEM_PRINCIPAL_ID,
            updated_by=SYSTEM_PRINCIPAL_ID,
        )
        self._session.add(asset)
        self._session.flush()
        version = FileAssetVersion(
            id=version_id,
            organization_id=SYSTEM_ORGANIZATION_ID,
            file_asset_id=asset.id,
            version_no=1,
            storage_bucket=metadata.bucket,
            storage_key=metadata.key,
            mime_type=normalized_media_type(metadata.media_type),
            byte_size=metadata.size_bytes,
            sha256=payload.sha256,
            etag=normalized_etag(metadata.etag),
            scan_status="pending",
            metadata_json={},
            created_at=created_at,
            created_by=SYSTEM_PRINCIPAL_ID,
        )
        self._session.add(version)
        self._session.flush()
        asset.current_version_id = version.id
        return asset

    @staticmethod
    def _mark_confirmed(
        upload: UploadSession,
        material: SourceMaterial,
        asset: FileAsset,
        confirmed_at: datetime,
    ) -> None:
        material.file_asset_id = asset.id
        material.upload_status = "confirmed"
        material.confirmed_at = confirmed_at
        material.confirmed_by = SYSTEM_PRINCIPAL_ID
        material.updated_by = SYSTEM_PRINCIPAL_ID
        material.lock_version += 1
        upload.status = "confirmed"
        upload.confirmed_at = confirmed_at
        upload.updated_by = SYSTEM_PRINCIPAL_ID
        upload.lock_version += 1

    def _create_job(
        self,
        upload: UploadSession,
        material: SourceMaterial,
        idempotency_key: str,
        payload: ConfirmUploadRequest,
    ) -> GenerationJob:
        return GenerationJob(
            id=new_uuid7(),
            organization_id=SYSTEM_ORGANIZATION_ID,
            project_id=upload.project_id,
            source_material_id=material.id,
            job_type="material.inspect",
            status="queued",
            progress_percent=0,
            progress_message="Upload confirmed; inspection queued",
            idempotency_key=idempotency_key,
            request_hash=self._request_hash(upload, payload),
            priority=100,
            created_by=SYSTEM_PRINCIPAL_ID,
            updated_by=SYSTEM_PRINCIPAL_ID,
        )

    def _validate_confirmation_payload(
        self, snapshot: UploadSnapshot, payload: ConfirmUploadRequest
    ) -> None:
        if snapshot.status != "created" or snapshot.expires_at <= utc_now():
            raise self._upload_rejected("The upload session is no longer confirmable.")
        if payload.size_bytes != snapshot.size_bytes or payload.sha256 != snapshot.sha256:
            raise self._upload_rejected("The confirmation does not match the upload session.")

    def _validate_object(
        self,
        snapshot: UploadSnapshot,
        payload: ConfirmUploadRequest,
        metadata: ObjectMetadata,
    ) -> None:
        matches = (
            metadata.bucket == snapshot.bucket
            and metadata.key == snapshot.key
            and normalized_etag(metadata.etag) == normalized_etag(payload.etag)
            and metadata.size_bytes == snapshot.size_bytes
            and normalized_media_type(metadata.media_type) == snapshot.media_type
            and metadata.sha256 == snapshot.sha256
        )
        if not matches:
            raise self._upload_rejected("The uploaded object metadata does not match the session.")

    @staticmethod
    def _request_hash(upload: UploadSession, payload: ConfirmUploadRequest) -> str:
        canonical = json.dumps(
            {
                "project_id": str(upload.project_id),
                "material_id": str(upload.material_id),
                **payload.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _upload_rejected(message: str) -> ApiError:
        return ApiError(status_code=409, code="UPLOAD_REJECTED", message=message)

    def _delete_best_effort(self, bucket: str, key: str, *, role: str) -> None:
        try:
            self._storage.delete(bucket=bucket, key=key)
        except ObjectStorageError as exc:
            logger.warning(
                "object_storage_cleanup_failed",
                extra={"object_role": role, "error_type": type(exc).__name__},
            )
