"""Upload session creation and presigned PUT orchestration."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import PurePosixPath, PureWindowsPath
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.uploads.models import SourceMaterial, UploadSession
from apps.api.uploads.schemas import CreateUploadSessionRequest, UploadSessionRead
from apps.api.uploads.storage import ObjectStorage, ObjectStorageError

ALLOWED_MEDIA_TYPES = frozenset({"application/pdf"})
MIN_PRESIGNED_URL_TTL = timedelta(seconds=1)


class PersistedUploadSessionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    upload_session_id: UUID
    material_id: UUID
    required_headers: dict[str, str]
    expires_at: datetime


def safe_filename(filename: str) -> str:
    candidate = filename.strip()
    if (
        not candidate
        or candidate != PurePosixPath(candidate).name
        or candidate != PureWindowsPath(candidate).name
        or any(ord(character) < 32 for character in candidate)
    ):
        raise ApiError(
            status_code=422,
            code="UPLOAD_REJECTED",
            message="The upload filename is unsafe.",
            details={"field": "filename"},
        )
    return candidate


def normalized_media_type(value: str) -> str:
    return value.split(";", 1)[0].strip().lower()


class UploadSessionService:
    def __init__(
        self,
        *,
        session: Session,
        storage: ObjectStorage,
        actor: ActorContext,
        bucket: str,
        ttl_seconds: int,
        max_size_bytes: int,
    ) -> None:
        self._session = session
        self._storage = storage
        self._actor = actor
        self._bucket = bucket
        self._ttl_seconds = ttl_seconds
        self._max_size_bytes = max_size_bytes

    def create_session(
        self,
        project_id: UUID,
        payload: CreateUploadSessionRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> UploadSessionRead:
        filename = safe_filename(payload.filename)
        media_type = normalized_media_type(payload.media_type)
        self._validate_upload_request(media_type=media_type, size_bytes=payload.size_bytes)
        idempotency_payload = {
            "project_id": str(project_id),
            **payload.model_dump(mode="json"),
        }
        idempotency = IdempotencyService(
            self._session,
            self._actor.organization_id,
            ttl_seconds=self._ttl_seconds,
        )
        with self._session.begin():
            replay = idempotency.lookup(
                scope="material_uploads.create",
                key=idempotency_key,
                payload=idempotency_payload,
                authorize=lambda: self._require_project(project_id, for_update=True),
            )
        if replay is not None:
            return self._present_result(project_id, replay)

        upload_id = new_uuid7()
        material_id = new_uuid7()
        key = (
            f"organizations/{self._actor.organization_id}/projects/{project_id}/materials/"
            f"{material_id}/uploads/{upload_id}/{filename}"
        )
        expires_at = utc_now() + timedelta(seconds=self._ttl_seconds)
        persisted = PersistedUploadSessionResult(
            upload_session_id=upload_id,
            material_id=material_id,
            required_headers={"Content-Type": media_type},
            expires_at=expires_at,
        )

        def command() -> CommandResult:
            self._require_project(project_id, for_update=True)
            self._persist_upload_session(
                project_id=project_id,
                upload_id=upload_id,
                material_id=material_id,
                filename=filename,
                media_type=media_type,
                key=key,
                expires_at=expires_at,
                payload=payload,
            )
            EventWriter(self._session, self._actor.organization_id).append(
                project_id=project_id,
                event_type="material.upload.created",
                resource=EventResource(type="source_material", id=material_id),
                payload={"upload_session_id": str(upload_id), "status": "created"},
                request_id=request_id,
            )
            return CommandResult(
                status_code=201,
                body=persisted.model_dump(mode="json"),
                resource_type="upload_session",
                resource_id=upload_id,
            )

        with self._session.begin():
            result = idempotency.execute(
                scope="material_uploads.create",
                key=idempotency_key,
                payload=idempotency_payload,
                authorize=lambda: self._require_project(project_id, for_update=True),
                command=command,
            )
        return self._present_result(project_id, result)

    def _require_project(self, project_id: UUID, *, for_update: bool = False) -> None:
        project = ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.EDIT,
            for_update=for_update,
        )
        if project.status == "archived":
            raise ApiError(
                status_code=409,
                code="PRECONDITION_NOT_MET",
                message="The project cannot accept uploads.",
            )

    def _present_result(self, project_id: UUID, result: CommandResult) -> UploadSessionRead:
        persisted = PersistedUploadSessionResult.model_validate(result.body)
        with self._session.begin():
            self._require_project(project_id)
            upload = self._session.scalar(
                select(UploadSession).where(
                    UploadSession.id == persisted.upload_session_id,
                    UploadSession.organization_id == self._actor.organization_id,
                    UploadSession.project_id == project_id,
                    UploadSession.material_id == persisted.material_id,
                    UploadSession.status == "created",
                    UploadSession.deleted_at.is_(None),
                )
            )
            if upload is None:
                raise ApiError(
                    status_code=409,
                    code="PRECONDITION_NOT_MET",
                    message="The upload session is no longer available.",
                )
            bucket = upload.storage_bucket
            key = upload.storage_key
            expires_at = upload.expires_at
        remaining = expires_at - utc_now()
        if remaining < MIN_PRESIGNED_URL_TTL:
            raise ApiError(
                status_code=409,
                code="PRECONDITION_NOT_MET",
                message="The upload session has expired.",
            )
        return UploadSessionRead(
            upload_session_id=persisted.upload_session_id,
            material_id=persisted.material_id,
            upload_url=self._presigned_url(bucket=bucket, key=key, expires=remaining),
            required_headers=persisted.required_headers,
            expires_at=expires_at,
        )

    def _presigned_url(self, *, bucket: str, key: str, expires: timedelta) -> str:
        try:
            return self._storage.create_presigned_put(
                bucket=bucket,
                key=key,
                expires=expires,
            )
        except ObjectStorageError as exc:
            raise ApiError(
                status_code=503,
                code="OBJECT_STORAGE_UNAVAILABLE",
                message="The upload service is temporarily unavailable.",
                retryable=True,
            ) from exc

    def _persist_upload_session(
        self,
        *,
        project_id: UUID,
        upload_id: UUID,
        material_id: UUID,
        filename: str,
        media_type: str,
        key: str,
        expires_at: datetime,
        payload: CreateUploadSessionRequest,
    ) -> None:
        material = SourceMaterial(
            id=material_id,
            organization_id=self._actor.organization_id,
            project_id=project_id,
            material_kind="textbook",
            file_asset_id=None,
            original_filename=filename,
            mime_type=media_type,
            upload_status="pending_upload",
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        upload = UploadSession(
            id=upload_id,
            organization_id=self._actor.organization_id,
            project_id=project_id,
            material_id=material_id,
            storage_bucket=self._bucket,
            storage_key=key,
            filename=filename,
            expected_media_type=media_type,
            expected_size_bytes=payload.size_bytes,
            expected_sha256=payload.sha256,
            status="created",
            expires_at=expires_at,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add_all((material, upload))

    def _validate_upload_request(self, *, media_type: str, size_bytes: int) -> None:
        if media_type not in ALLOWED_MEDIA_TYPES:
            raise ApiError(
                status_code=409,
                code="UPLOAD_REJECTED",
                message="The material media type is not allowed.",
            )
        if size_bytes > self._max_size_bytes:
            raise ApiError(
                status_code=409,
                code="UPLOAD_REJECTED",
                message="The material exceeds the upload size limit.",
            )
