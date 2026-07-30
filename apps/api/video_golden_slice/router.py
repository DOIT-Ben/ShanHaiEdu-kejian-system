from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from apps.api.creation.schemas import (
    AdoptGenerationResultRequest,
    AdoptionEnvelope,
    SaveToProjectOperationEnvelope,
)
from apps.api.dependencies import get_object_storage, get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.identity.dependencies import get_actor_context
from apps.api.jobs.schemas import AcceptedJobEnvelope
from apps.api.settings import Settings
from apps.api.uploads.storage import ObjectStorage, ObjectStorageError
from apps.api.video_golden_slice.schemas import (
    SaveVideoAdoptionRequest,
    StartVideoGenerationRequest,
    VideoGoldenSliceEnvelope,
)
from apps.api.video_golden_slice.service import VideoGoldenSliceService

router = APIRouter(
    prefix="/api/v2/projects/{project_id}/lessons/{lesson_id}/video",
    tags=["video-golden-slice"],
)
IdempotencyHeader = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=128),
]


def _service(
    request: Request,
    session: Session,
    actor: ActorContext,
) -> VideoGoldenSliceService:
    settings = cast(Settings, request.app.state.settings)
    return VideoGoldenSliceService(
        session,
        actor,
        idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
    )


@router.get(
    "",
    response_model=VideoGoldenSliceEnvelope,
    operation_id="getLessonVideoGoldenSlice",
)
def get_lesson_video_golden_slice(
    project_id: UUID,
    lesson_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> VideoGoldenSliceEnvelope:
    with session.begin():
        data = _service(request, session, actor).get(project_id, lesson_id)
    return VideoGoldenSliceEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/generations",
    response_model=AcceptedJobEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startLessonVideoGeneration",
)
def start_lesson_video_generation(
    project_id: UUID,
    lesson_id: UUID,
    payload: StartVideoGenerationRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> AcceptedJobEnvelope:
    with session.begin():
        data = _service(request, session, actor).start(
            project_id,
            lesson_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return AcceptedJobEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/results/{result_id}/adoptions",
    response_model=AdoptionEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="adoptLessonVideoResult",
)
def adopt_lesson_video_result(
    project_id: UUID,
    lesson_id: UUID,
    result_id: UUID,
    payload: AdoptGenerationResultRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> AdoptionEnvelope:
    with session.begin():
        data = _service(request, session, actor).adopt(
            project_id,
            lesson_id,
            result_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return AdoptionEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/adoptions/{adoption_id}/save",
    response_model=SaveToProjectOperationEnvelope,
    operation_id="saveLessonVideoAdoption",
)
def save_lesson_video_adoption(
    project_id: UUID,
    lesson_id: UUID,
    adoption_id: UUID,
    payload: SaveVideoAdoptionRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> SaveToProjectOperationEnvelope:
    with session.begin():
        data = _service(request, session, actor).save(
            project_id,
            lesson_id,
            adoption_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return SaveToProjectOperationEnvelope(data=data, request_id=request.state.request_id)


@router.get(
    "/results/{result_id}/content",
    response_class=FileResponse,
    operation_id="playLessonVideoResult",
)
def play_lesson_video_result(
    project_id: UUID,
    lesson_id: UUID,
    result_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> FileResponse:
    settings = cast(Settings, request.app.state.settings)
    with session.begin():
        version = _service(request, session, actor).playback_file(
            project_id,
            lesson_id,
            result_id,
        )
    temporary = tempfile.NamedTemporaryFile(
        prefix="shanhaiedu-playback-", suffix=".mp4", delete=False
    )
    path = Path(temporary.name)
    temporary.close()
    try:
        metadata = storage.download_to_path(
            bucket=version.storage_bucket,
            key=version.storage_key,
            destination=path,
            max_bytes=settings.video_provider_max_download_bytes,
        )
    except ObjectStorageError as exc:
        path.unlink(missing_ok=True)
        raise ApiError(
            status_code=503,
            code="VIDEO_PLAYBACK_UNAVAILABLE",
            message="The video file is temporarily unavailable.",
            retryable=True,
        ) from exc
    if (
        metadata.media_type != version.mime_type
        or metadata.size_bytes != version.byte_size
        or metadata.sha256 != version.sha256
    ):
        path.unlink(missing_ok=True)
        raise ApiError(
            status_code=409,
            code="VIDEO_FILE_FACT_MISMATCH",
            message="The stored video no longer matches its immutable file facts.",
        )
    return FileResponse(
        path,
        media_type="video/mp4",
        headers={"Cache-Control": "private, no-store"},
        background=BackgroundTask(path.unlink, missing_ok=True),
    )
