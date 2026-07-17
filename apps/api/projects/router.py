"""Stage-zero project HTTP endpoints."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.models import SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import (
    CreateProjectRequest,
    PageMeta,
    ProjectEnvelope,
    ProjectListData,
    ProjectListEnvelope,
    ProjectRead,
)
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.reliability.sse import EventReplayRepository, parse_last_event_id, stream_events
from apps.api.settings import Settings

router = APIRouter(prefix="/api/v2/projects", tags=["projects"])


def repository(session: Session) -> ProjectRepository:
    return ProjectRepository(session, SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID)


@router.post(
    "",
    response_model=ProjectEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="createProject",
)
def create_project(
    payload: CreateProjectRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    session: Annotated[Session, Depends(get_session)],
) -> ProjectEnvelope:
    settings = cast(Settings, request.app.state.settings)

    def command() -> CommandResult:
        project = repository(session).create(payload)
        EventWriter(session, SYSTEM_ORGANIZATION_ID).append(
            project_id=project.id,
            event_type="project.created",
            resource=EventResource(type="project", id=project.id),
            payload={"status": project.status},
            request_id=request.state.request_id,
        )
        return CommandResult(
            status_code=201,
            body=ProjectRead.model_validate(project).model_dump(mode="json"),
            resource_type="project",
            resource_id=project.id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            SYSTEM_ORGANIZATION_ID,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope="projects.create",
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            command=command,
        )
    return ProjectEnvelope(
        data=ProjectRead.model_validate(result.body),
        request_id=request.state.request_id,
    )


@router.get("", response_model=ProjectListEnvelope, operation_id="listProjects")
def list_projects(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    page_cursor: Annotated[str | None, Query(alias="page[cursor]")] = None,
    page_limit: Annotated[int, Query(alias="page[limit]", ge=1, le=100)] = 20,
) -> ProjectListEnvelope:
    try:
        cursor = UUID(page_cursor) if page_cursor else None
    except ValueError as exc:
        raise ApiError(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The page cursor is invalid.",
            details={"field": "page[cursor]"},
        ) from exc
    projects, next_cursor = repository(session).list_page(cursor=cursor, limit=page_limit)
    return ProjectListEnvelope(
        data=ProjectListData(items=[ProjectRead.model_validate(project) for project in projects]),
        meta=PageMeta(next_cursor=next_cursor),
        request_id=request.state.request_id,
    )


@router.get("/{project_id}", response_model=ProjectEnvelope, operation_id="getProject")
def get_project(
    project_id: UUID,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> ProjectEnvelope:
    project = repository(session).get(project_id)
    if project is None:
        raise ApiError(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message="The project was not found.",
        )
    response.headers["ETag"] = f'W/"{project.lock_version}"'
    return ProjectEnvelope(
        data=ProjectRead.model_validate(project),
        request_id=request.state.request_id,
    )


@router.get(
    "/{project_id}/events/stream",
    response_class=StreamingResponse,
    operation_id="streamProjectEvents",
)
def stream_project_events(
    project_id: UUID,
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    factory = cast(sessionmaker[Session] | None, request.app.state.session_factory)
    if factory is None:
        raise ApiError(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="Database persistence is not configured.",
            retryable=True,
        )
    cursor = parse_last_event_id(last_event_id)
    with factory() as session:
        project = repository(session).get(project_id)
        if project is None:
            raise ApiError(
                status_code=404,
                code="PROJECT_NOT_FOUND",
                message="The project was not found.",
            )
        EventReplayRepository(session).replay(
            project_id=project_id,
            after_sequence=cursor,
            limit=1,
        )
    settings = cast(Settings, request.app.state.settings)
    return StreamingResponse(
        stream_events(
            factory,
            project_id=project_id,
            after_sequence=cursor,
            resource=None,
            poll_seconds=settings.sse_poll_seconds,
            heartbeat_seconds=settings.sse_heartbeat_seconds,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
