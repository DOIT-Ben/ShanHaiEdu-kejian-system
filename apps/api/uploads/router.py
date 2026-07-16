"""Project material upload HTTP endpoints."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from apps.api.dependencies import get_object_storage, get_session
from apps.api.jobs.schemas import AcceptedJobEnvelope
from apps.api.settings import Settings
from apps.api.uploads.confirmation_service import UploadConfirmationService
from apps.api.uploads.schemas import (
    ConfirmUploadRequest,
    CreateUploadSessionRequest,
    UploadSessionEnvelope,
)
from apps.api.uploads.session_service import UploadSessionService
from apps.api.uploads.storage import ObjectStorage

router = APIRouter(prefix="/api/v2/projects/{project_id}/materials", tags=["materials"])


def session_service(
    request: Request,
    session: Session,
    storage: ObjectStorage,
) -> UploadSessionService:
    settings = cast(Settings, request.app.state.settings)
    return UploadSessionService(
        session=session,
        storage=storage,
        bucket=settings.object_storage_bucket,
        ttl_seconds=settings.upload_session_ttl_seconds,
        max_size_bytes=settings.max_upload_size_bytes,
    )


@router.post(
    "/uploads",
    response_model=UploadSessionEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="createMaterialUploadSession",
)
def create_upload_session(
    project_id: UUID,
    payload: CreateUploadSessionRequest,
    request: Request,
    _idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> UploadSessionEnvelope:
    created = session_service(request, session, storage).create_session(project_id, payload)
    return UploadSessionEnvelope(data=created, request_id=request.state.request_id)


@router.post(
    "/{material_id}/confirm",
    response_model=AcceptedJobEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="confirmMaterialUpload",
)
def confirm_upload(
    project_id: UUID,
    material_id: UUID,
    payload: ConfirmUploadRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> AcceptedJobEnvelope:
    accepted = UploadConfirmationService(session=session, storage=storage).confirm(
        project_id=project_id,
        material_id=material_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )
    return AcceptedJobEnvelope(data=accepted, request_id=request.state.request_id)
