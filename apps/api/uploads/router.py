"""Project material upload HTTP endpoints."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from apps.api.dependencies import get_object_storage, get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService
from apps.api.jobs.schemas import AcceptedJobEnvelope
from apps.api.settings import Settings
from apps.api.uploads.confirmation_service import UploadConfirmationService
from apps.api.uploads.repository import SourceMaterialRepository
from apps.api.uploads.schemas import (
    ConfirmUploadRequest,
    CreateUploadSessionRequest,
    SourceMaterialListData,
    SourceMaterialListEnvelope,
    SourceMaterialPageMeta,
    SourceMaterialRead,
    UploadSessionEnvelope,
)
from apps.api.uploads.session_service import UploadSessionService
from apps.api.uploads.storage import ObjectStorage

router = APIRouter(prefix="/api/v2/projects/{project_id}/materials", tags=["materials"])


@router.get("", response_model=SourceMaterialListEnvelope, operation_id="listProjectMaterials")
def list_project_materials(
    project_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
    page_cursor: Annotated[str | None, Query(alias="page[cursor]")] = None,
    page_limit: Annotated[int, Query(alias="page[limit]", ge=1, le=100)] = 20,
) -> SourceMaterialListEnvelope:
    ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    materials, next_cursor = SourceMaterialRepository(session, actor.organization_id).list_page(
        project_id,
        cursor=_parse_page_cursor(page_cursor),
        limit=page_limit,
    )
    return SourceMaterialListEnvelope(
        data=SourceMaterialListData(
            items=[SourceMaterialRead.model_validate(material) for material in materials]
        ),
        meta=SourceMaterialPageMeta(next_cursor=next_cursor),
        request_id=request.state.request_id,
    )


def _parse_page_cursor(value: str | None) -> UUID | None:
    try:
        return UUID(value) if value else None
    except ValueError as exc:
        raise ApiError(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The page cursor is invalid.",
            details={"field": "page[cursor]"},
        ) from exc


def session_service(
    request: Request,
    session: Session,
    storage: ObjectStorage,
    actor: ActorContext,
) -> UploadSessionService:
    settings = cast(Settings, request.app.state.settings)
    return UploadSessionService(
        session=session,
        storage=storage,
        actor=actor,
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
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> UploadSessionEnvelope:
    created = session_service(request, session, storage, actor).create_session(
        project_id,
        payload,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )
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
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> AcceptedJobEnvelope:
    accepted = UploadConfirmationService(session=session, storage=storage, actor=actor).confirm(
        project_id=project_id,
        material_id=material_id,
        idempotency_key=idempotency_key,
        payload=payload,
        request_id=request.state.request_id,
        idempotency_ttl_seconds=cast(Settings, request.app.state.settings).idempotency_ttl_seconds,
    )
    return AcceptedJobEnvelope(data=accepted, request_id=request.state.request_id)
