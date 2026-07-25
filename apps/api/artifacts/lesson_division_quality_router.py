"""HTTP command for exact lesson-division quality validation."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from apps.api.artifacts.lesson_division_quality_service import (
    LessonDivisionQualityValidationService,
)
from apps.api.dependencies import get_session
from apps.api.identity.context import ActorContext
from apps.api.identity.dependencies import get_actor_context
from apps.api.settings import Settings
from apps.api.workflows.schemas import AcceptedNodeRunEnvelope

router = APIRouter(tags=["artifacts"])


@router.post(
    "/api/v2/projects/{project_id}/lesson-division/artifact-versions/"
    "{artifact_version_id}/quality-validations",
    response_model=AcceptedNodeRunEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startLessonDivisionQualityValidation",
)
def start_lesson_division_quality_validation(
    project_id: UUID,
    artifact_version_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> AcceptedNodeRunEnvelope:
    settings = cast(Settings, request.app.state.settings)
    with session.begin():
        accepted = LessonDivisionQualityValidationService(
            session,
            actor,
            idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
        ).start(
            project_id,
            artifact_version_id,
            idempotency_key=idempotency_key,
        )
    return AcceptedNodeRunEnvelope(data=accepted, request_id=request.state.request_id)
