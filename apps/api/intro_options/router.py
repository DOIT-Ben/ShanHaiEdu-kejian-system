"""Runtime HTTP routes for Intro option queries and teacher selections."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService
from apps.api.intro_options.query_service import IntroOptionsQueryService, to_public_selection
from apps.api.intro_options.runtime import IntroOptionRuntimeService
from apps.api.intro_options.schemas import (
    IntroOptionsEnvelope,
    IntroSelectionEnvelope,
    PrepareIntroOptionGenerationRequest,
    SelectIntroOptionRequest,
)
from apps.api.intro_selections.service import IntroSelectionService
from apps.api.lessons.intro_port import IntroLessonReader
from apps.api.lessons.repository import LessonRepository
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.settings import Settings
from apps.api.workflows.models import NodeRun
from apps.api.workflows.schemas import NodeRunEnvelope, NodeRunRead

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
    "/api/v2/lessons/{lesson_id}/intro-options/node-runs",
    response_model=NodeRunEnvelope,
    operation_id="prepareIntroOptionGeneration",
)
def prepare_intro_option_generation(
    lesson_id: UUID,
    payload: PrepareIntroOptionGenerationRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> NodeRunEnvelope:
    settings = cast(Settings, request.app.state.settings)
    with session.begin():
        lesson = LessonRepository(session, actor).get(lesson_id, for_update=True)
        if lesson is None or lesson.status != "active":
            raise ApiError(
                status_code=404,
                code="LESSON_NOT_FOUND",
                message="The lesson was not found.",
            )

        def command() -> CommandResult:
            node_id = IntroOptionRuntimeService(session, actor).stage_generation(
                project_id=lesson.project_id,
                lesson_unit_id=lesson.id,
                generation_mode=payload.generation_mode,
                source_artifact_version_id=payload.source_artifact_version_id,
            )
            node = session.get(NodeRun, node_id)
            if node is None:
                raise ApiError(
                    status_code=409,
                    code="INTRO_OPTION_RUNTIME_INVALID",
                    message="The prepared Intro NodeRun is unavailable.",
                )
            data = NodeRunRead.model_validate(node)
            return CommandResult(
                status_code=200,
                body=data.model_dump(mode="json"),
                resource_type="node_run",
                resource_id=node.id,
            )

        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"intro-options.prepare:{lesson_id}:{actor.principal_id}",
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            authorize=lambda: ProjectAccessService(session, actor).require(
                lesson.project_id,
                ProjectAction.GENERATE,
                for_update=True,
            ),
            command=command,
        )
    return NodeRunEnvelope(
        data=NodeRunRead.model_validate(result.body),
        request_id=request.state.request_id,
    )


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
