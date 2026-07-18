"""Stage-zero project HTTP endpoints."""

from __future__ import annotations

import re
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService
from apps.api.projects.policy_schemas import (
    AutomationPolicyEnvelope,
    UpdateAutomationPolicyRequest,
)
from apps.api.projects.policy_service import AutomationPolicyService
from apps.api.projects.read_service import ProjectReadService
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
ETAG_PATTERN = re.compile(r'^(?:W/)?"(?P<version>[1-9][0-9]*)"$')


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
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> ProjectEnvelope:
    settings = cast(Settings, request.app.state.settings)

    def command() -> CommandResult:
        project = ProjectRepository(session, actor).create(payload)
        data = ProjectReadService(session, actor).present(project)
        EventWriter(session, actor.organization_id).append(
            project_id=project.id,
            event_type="project.created",
            resource=EventResource(type="project", id=project.id),
            payload={"status": project.status},
            request_id=request.state.request_id,
        )
        return CommandResult(
            status_code=201,
            body=data.model_dump(mode="json"),
            resource_type="project",
            resource_id=project.id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"projects.create:{actor.principal_id}",
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            authorize=lambda: require_project_creator(actor),
            command=command,
        )
    return ProjectEnvelope(
        data=ProjectRead.model_validate(result.body),
        request_id=request.state.request_id,
    )


@router.get("", response_model=ProjectListEnvelope, operation_id="listProjects")
def list_projects(
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
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
    projects, next_cursor = ProjectRepository(session, actor).list_page(
        cursor=cursor,
        limit=page_limit,
    )
    return ProjectListEnvelope(
        data=ProjectListData(items=ProjectReadService(session, actor).present_many(projects)),
        meta=PageMeta(next_cursor=next_cursor),
        request_id=request.state.request_id,
    )


@router.get("/{project_id}", response_model=ProjectEnvelope, operation_id="getProject")
def get_project(
    project_id: UUID,
    request: Request,
    response: Response,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> ProjectEnvelope:
    project = ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    response.headers["ETag"] = f'W/"{project.lock_version}"'
    return ProjectEnvelope(
        data=ProjectReadService(session, actor).present(project),
        request_id=request.state.request_id,
    )


@router.get(
    "/{project_id}/automation-policy",
    response_model=AutomationPolicyEnvelope,
    operation_id="getProjectAutomationPolicy",
)
def get_project_automation_policy(
    project_id: UUID,
    request: Request,
    response: Response,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> AutomationPolicyEnvelope:
    policy = AutomationPolicyService(session, actor).get(project_id)
    response.headers["ETag"] = f'W/"{policy.policy_version}"'
    return AutomationPolicyEnvelope(data=policy, request_id=request.state.request_id)


@router.patch(
    "/{project_id}/automation-policy",
    response_model=AutomationPolicyEnvelope,
    operation_id="updateProjectAutomationPolicy",
)
def update_project_automation_policy(
    project_id: UUID,
    payload: UpdateAutomationPolicyRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8)],
    if_match: Annotated[str, Header(alias="If-Match")],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> AutomationPolicyEnvelope:
    match = ETAG_PATTERN.fullmatch(if_match.strip())
    if match is None:
        raise ApiError(
            status_code=422,
            code="VALIDATION_FAILED",
            message="If-Match must contain a valid automation policy ETag.",
            details={"field": "If-Match"},
        )
    settings = cast(Settings, request.app.state.settings)
    with session.begin():
        policy = AutomationPolicyService(session, actor).update(
            project_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
            expected_version=int(match.group("version")),
        )
    response.headers["ETag"] = f'W/"{policy.policy_version}"'
    return AutomationPolicyEnvelope(data=policy, request_id=request.state.request_id)


@router.get(
    "/{project_id}/events/stream",
    response_class=StreamingResponse,
    operation_id="streamProjectEvents",
)
def stream_project_events(
    project_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
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
        ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
        EventReplayRepository(session, actor.organization_id).replay(
            project_id=project_id,
            after_sequence=cursor,
            limit=1,
        )
    settings = cast(Settings, request.app.state.settings)
    return StreamingResponse(
        stream_events(
            factory,
            organization_id=actor.organization_id,
            project_id=project_id,
            after_sequence=cursor,
            resource=None,
            poll_seconds=settings.sse_poll_seconds,
            heartbeat_seconds=settings.sse_heartbeat_seconds,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def require_project_creator(actor: ActorContext) -> None:
    if actor.user_id is None or actor.is_system:
        raise ApiError(
            status_code=403,
            code="PERMISSION_DENIED",
            message="Project creation requires a user actor.",
        )
