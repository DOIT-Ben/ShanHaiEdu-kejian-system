"""Runtime HTTP routes for Intro option queries and teacher selections."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from apps.api.dependencies import get_session
from apps.api.identity.context import ActorContext
from apps.api.identity.dependencies import get_actor_context
from apps.api.intro_options.query_service import IntroOptionsQueryService, to_public_selection
from apps.api.intro_options.schemas import (
    IntroOptionsEnvelope,
    IntroSelectionEnvelope,
    SelectIntroOptionRequest,
)
from apps.api.intro_selections.service import IntroSelectionService
from apps.api.lessons.intro_port import IntroLessonReader
from apps.api.settings import Settings

router = APIRouter(tags=["intro-options"])


@router.get(
    "/api/v2/lessons/{lesson_id}/intro-options",
    response_model=IntroOptionsEnvelope,
    operation_id="getLessonIntroOptions",
)
def get_lesson_intro_options(
    lesson_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> IntroOptionsEnvelope:
    with session.begin():
        data = IntroOptionsQueryService(session, actor).get(lesson_id)
    return IntroOptionsEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/api/v2/lessons/{lesson_id}/intro-selections",
    response_model=IntroSelectionEnvelope,
    status_code=201,
    operation_id="selectLessonIntroOption",
)
def select_lesson_intro_option(
    lesson_id: UUID,
    payload: SelectIntroOptionRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> IntroSelectionEnvelope:
    settings = cast(Settings, request.app.state.settings)
    with session.begin():
        lesson = IntroLessonReader(session, actor).require_view(lesson_id)
        selection = IntroSelectionService(session, actor).select_teacher(
            project_id=lesson.project_id,
            lesson_unit_id=lesson.id,
            artifact_version_id=payload.artifact_version_id,
            option_key=payload.option_key,
            reason="Selected by a teacher through the runtime API.",
            idempotency_key=idempotency_key,
            ttl_seconds=settings.idempotency_ttl_seconds,
        )
    return IntroSelectionEnvelope(
        data=to_public_selection(selection),
        request_id=request.state.request_id,
    )
