"""Prepare one exact lesson-plan generation NodeRun."""

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
from apps.api.lessons.lesson_plan_runtime import LessonPlanRuntimeService
from apps.api.lessons.repository import LessonRepository
from apps.api.lessons.runtime_service import LessonDivisionRuntimeService
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.settings import Settings
from apps.api.workflows.schemas import (
    NodeRunEnvelope,
    NodeRunRead,
    PrepareLessonDivisionRequest,
)

router = APIRouter(tags=["workflows"])


@router.post(
    "/api/v2/projects/{project_id}/lesson-division/node-runs",
    response_model=NodeRunEnvelope,
    operation_id="prepareLessonDivision",
)
def prepare_lesson_division(
    project_id: UUID,
    payload: PrepareLessonDivisionRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> NodeRunEnvelope:
    settings = cast(Settings, request.app.state.settings)

    def command() -> CommandResult:
        runtime = LessonDivisionRuntimeService(session, actor)
        node_id = runtime.prepare(
            project_id,
            material_scope_artifact_version_id=payload.material_scope_artifact_version_id,
        )
        data = runtime.read_node(node_id)
        return CommandResult(
            status_code=200,
            body=data.model_dump(mode="json"),
            resource_type="node_run",
            resource_id=node_id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"lesson-division.prepare:{project_id}:{actor.principal_id}",
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            authorize=lambda: ProjectAccessService(session, actor).require(
                project_id,
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
    "/api/v2/lessons/{lesson_id}/lesson-plan/node-runs",
    response_model=NodeRunEnvelope,
    operation_id="prepareLessonPlanGeneration",
)
def prepare_lesson_plan_generation(
    lesson_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> NodeRunEnvelope:
    settings = cast(Settings, request.app.state.settings)

    def authorize() -> object:
        lesson = LessonRepository(session, actor).get(lesson_id, for_update=True)
        if lesson is None or lesson.status != "active":
            raise ApiError(
                status_code=404,
                code="LESSON_NOT_FOUND",
                message="The lesson was not found.",
            )
        return ProjectAccessService(session, actor).require(
            lesson.project_id,
            ProjectAction.GENERATE,
            for_update=True,
        )

    def command() -> CommandResult:
        runtime = LessonPlanRuntimeService(session, actor)
        node_id = runtime.stage_generation(lesson_id)
        data = runtime.read_node(node_id)
        return CommandResult(
            status_code=200,
            body=data.model_dump(mode="json"),
            resource_type="node_run",
            resource_id=node_id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"lesson-plan.prepare:{lesson_id}:{actor.principal_id}",
            key=idempotency_key,
            payload={},
            authorize=authorize,
            command=command,
        )
    return NodeRunEnvelope(
        data=NodeRunRead.model_validate(result.body),
        request_id=request.state.request_id,
    )
