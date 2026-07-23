"""Lesson collection, detail, and branch configuration endpoints."""

from __future__ import annotations

import re
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService
from apps.api.lessons.domain import (
    BranchConfigurationChange,
    BranchKey,
    LessonCollectionEdit,
    workflow_status_for_branch,
)
from apps.api.lessons.material_scope_service import MaterialScopePreparationService
from apps.api.lessons.models import LessonBranchConfig, LessonUnit
from apps.api.lessons.repository import LessonRepository
from apps.api.lessons.schemas import (
    LessonBranchRead,
    LessonCollectionData,
    LessonCollectionEnvelope,
    LessonDivisionPreparationEnvelope,
    LessonDivisionPreparationRead,
    LessonEnvelope,
    LessonRead,
    PrepareLessonDivisionRequest,
    UpdateLessonBranchesRequest,
    UpdateLessonCollectionRequest,
)
from apps.api.lessons.service import LessonService
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.settings import Settings

router = APIRouter(tags=["lessons"])
ETAG_PATTERN = re.compile(r'^(?:W/)?"(?P<version>[1-9][0-9]*)"$')


@router.post(
    "/api/v2/projects/{project_id}/lesson-division-runs",
    response_model=LessonDivisionPreparationEnvelope,
    status_code=status.HTTP_201_CREATED,
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
) -> LessonDivisionPreparationEnvelope:
    settings = cast(Settings, request.app.state.settings)

    def command() -> CommandResult:
        prepared = MaterialScopePreparationService(session, actor).prepare(
            project_id,
            material_id=payload.material_id,
            material_parse_version_id=payload.material_parse_version_id,
            page_start=payload.page_start,
            page_end=payload.page_end,
            duration_minutes=payload.duration_minutes,
            requested_lesson_count=payload.requested_lesson_count,
            special_requirements=payload.special_requirements,
            request_id=request.state.request_id,
        )
        data = LessonDivisionPreparationRead.model_validate(prepared, from_attributes=True)
        return CommandResult(
            status_code=201,
            body=data.model_dump(mode="json"),
            resource_type="artifact",
            resource_id=prepared.material_scope_artifact_id,
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
    return LessonDivisionPreparationEnvelope(
        data=LessonDivisionPreparationRead.model_validate(result.body),
        request_id=request.state.request_id,
    )


@router.get(
    "/api/v2/projects/{project_id}/lessons",
    response_model=LessonCollectionEnvelope,
    operation_id="listProjectLessons",
)
def list_project_lessons(
    project_id: UUID,
    request: Request,
    response: Response,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> LessonCollectionEnvelope:
    project = ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    repository = LessonRepository(session, actor)
    lessons = repository.list_for_project(project_id)
    response.headers["ETag"] = weak_etag(project.lock_version)
    return LessonCollectionEnvelope(
        data=LessonCollectionData(
            items=[serialize_lesson(repository, lesson) for lesson in lessons],
            lock_version=project.lock_version,
        ),
        request_id=request.state.request_id,
    )


@router.patch(
    "/api/v2/projects/{project_id}/lessons",
    response_model=LessonCollectionEnvelope,
    operation_id="updateProjectLessons",
)
def update_project_lessons(
    project_id: UUID,
    payload: UpdateLessonCollectionRequest,
    request: Request,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> LessonCollectionEnvelope:
    expected_version = parse_etag(if_match)
    settings = cast(Settings, request.app.state.settings)
    request_payload = payload.model_dump(mode="json") | {"if_match": expected_version}

    def command() -> CommandResult:
        lessons = LessonService(session, actor).update_collection(
            project_id,
            expected_version=expected_version,
            items=tuple(
                LessonCollectionEdit(
                    id=item.id,
                    position=item.position,
                    title=item.title,
                    scope_summary=item.scope_summary,
                    objective_summary=item.objective_summary,
                    estimated_minutes=item.estimated_minutes,
                )
                for item in payload.items
            ),
            request_id=request.state.request_id,
        )
        project = ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
        repository = LessonRepository(session, actor)
        data = LessonCollectionData(
            items=[serialize_lesson(repository, lesson) for lesson in lessons],
            lock_version=project.lock_version,
        )
        return CommandResult(
            status_code=200,
            body=data.model_dump(mode="json"),
            resource_type="lesson_collection",
            resource_id=project_id,
        )

    with session.begin():
        ProjectAccessService(session, actor).require(project_id, ProjectAction.EDIT)
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"lessons.collection.update:{project_id}:{actor.principal_id}",
            key=idempotency_key,
            payload=request_payload,
            authorize=lambda: ProjectAccessService(session, actor).require(
                project_id,
                ProjectAction.EDIT,
                for_update=True,
            ),
            command=command,
        )
    data = LessonCollectionData.model_validate(result.body)
    response.headers["ETag"] = weak_etag(data.lock_version)
    return LessonCollectionEnvelope(data=data, request_id=request.state.request_id)


@router.get(
    "/api/v2/lessons/{lesson_id}",
    response_model=LessonEnvelope,
    operation_id="getLesson",
)
def get_lesson(
    lesson_id: UUID,
    request: Request,
    response: Response,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> LessonEnvelope:
    repository = LessonRepository(session, actor)
    lesson = repository.get(lesson_id)
    if lesson is None:
        raise lesson_not_found()
    ProjectAccessService(session, actor).require(lesson.project_id, ProjectAction.VIEW)
    response.headers["ETag"] = weak_etag(lesson.lock_version)
    return LessonEnvelope(
        data=serialize_lesson(repository, lesson),
        request_id=request.state.request_id,
    )


@router.patch(
    "/api/v2/lessons/{lesson_id}/branches",
    response_model=LessonEnvelope,
    operation_id="updateLessonBranches",
)
def update_lesson_branches(
    lesson_id: UUID,
    payload: UpdateLessonBranchesRequest,
    request: Request,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> LessonEnvelope:
    expected_version = parse_etag(if_match)
    settings = cast(Settings, request.app.state.settings)
    request_payload = payload.model_dump(mode="json") | {"if_match": expected_version}

    def command() -> CommandResult:
        updated = LessonService(session, actor).update_branches(
            lesson_id,
            expected_version=expected_version,
            changes={
                branch.branch_key: BranchConfigurationChange(
                    enabled=branch.enabled,
                    settings=branch.settings,
                )
                for branch in payload.branches
            },
            request_id=request.state.request_id,
        )
        data = serialize_lesson(LessonRepository(session, actor), updated)
        return CommandResult(
            status_code=200,
            body=data.model_dump(mode="json"),
            resource_type="lesson",
            resource_id=updated.id,
        )

    with session.begin():
        visible = LessonRepository(session, actor).get(lesson_id)
        if visible is None:
            raise lesson_not_found()
        ProjectAccessService(session, actor).require(visible.project_id, ProjectAction.EDIT)
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"lessons.branches.update:{lesson_id}:{actor.principal_id}",
            key=idempotency_key,
            payload=request_payload,
            authorize=lambda: require_lesson_access(
                session,
                actor,
                lesson_id,
                ProjectAction.EDIT,
            ),
            command=command,
        )
    data = LessonRead.model_validate(result.body)
    response.headers["ETag"] = weak_etag(data.lock_version)
    return LessonEnvelope(data=data, request_id=request.state.request_id)


def require_lesson_access(
    session: Session,
    actor: ActorContext,
    lesson_id: UUID,
    action: ProjectAction,
) -> LessonUnit:
    lesson = LessonRepository(session, actor).get(lesson_id, for_update=True)
    if lesson is None:
        raise lesson_not_found()
    ProjectAccessService(session, actor).require(
        lesson.project_id,
        action,
        for_update=True,
    )
    return lesson


def serialize_lesson(repository: LessonRepository, lesson: LessonUnit) -> LessonRead:
    configs = repository.list_branch_configs(lesson.id)
    by_key = {BranchKey(config.branch_key): config for config in configs}
    return LessonRead.model_validate(
        {
            "id": lesson.id,
            "project_id": lesson.project_id,
            "lesson_key": lesson.lesson_key,
            "position": lesson.position,
            "title": lesson.title,
            "scope_summary": lesson.scope_summary,
            "objective_summary": lesson.objective_summary,
            "estimated_minutes": lesson.estimated_minutes,
            "source_division_version_id": lesson.source_division_version_id,
            "status": lesson.status,
            "lock_version": lesson.lock_version,
            "branches": [serialize_branch(by_key[branch_key]) for branch_key in BranchKey],
            "created_at": lesson.created_at,
            "updated_at": lesson.updated_at,
        }
    )


def serialize_branch(config: LessonBranchConfig) -> LessonBranchRead:
    return LessonBranchRead(
        branch_key=BranchKey(config.branch_key),
        enabled=config.enabled,
        workflow_status=workflow_status_for_branch(enabled=config.enabled),
        settings=config.settings_json,
    )


def parse_etag(value: str) -> int:
    match = ETAG_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ApiError(
            status_code=422,
            code="VALIDATION_FAILED",
            message="If-Match must contain a valid resource ETag.",
            details={"field": "If-Match"},
        )
    return int(match.group("version"))


def weak_etag(version: int) -> str:
    return f'W/"{version}"'


def lesson_not_found() -> ApiError:
    return ApiError(
        status_code=404,
        code="LESSON_NOT_FOUND",
        message="The lesson was not found.",
    )
