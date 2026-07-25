"""Generation job fact query endpoint."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService
from apps.api.jobs.repository import GenerationJobRepository
from apps.api.jobs.schemas import (
    GenerationJobEnvelope,
    GenerationJobListData,
    GenerationJobListEnvelope,
    GenerationJobPageMeta,
    GenerationJobRead,
)
from apps.api.jobs.service import GenerationJobService
from apps.api.pagination import parse_uuid_page_cursor
from apps.api.reliability.sse import EventReplayRepository, parse_last_event_id, stream_events
from apps.api.settings import Settings

router = APIRouter(prefix="/api/v2/generation-jobs", tags=["generation-jobs"])
project_router = APIRouter(tags=["generation-jobs"])


@project_router.get(
    "/api/v2/projects/{project_id}/generation-jobs",
    response_model=GenerationJobListEnvelope,
    operation_id="listProjectGenerationJobs",
)
def list_project_generation_jobs(
    project_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
    lesson_id: Annotated[UUID | None, Query()] = None,
    page_cursor: Annotated[str | None, Query(alias="page[cursor]")] = None,
    page_limit: Annotated[int, Query(alias="page[limit]", ge=1, le=100)] = 20,
) -> GenerationJobListEnvelope:
    ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    jobs, next_cursor = GenerationJobRepository(session, actor.organization_id).list_page(
        project_id,
        cursor=parse_uuid_page_cursor(page_cursor),
        limit=page_limit,
        lesson_unit_id=lesson_id,
    )
    return GenerationJobListEnvelope(
        data=GenerationJobListData(items=[GenerationJobRead.model_validate(job) for job in jobs]),
        meta=GenerationJobPageMeta(next_cursor=next_cursor),
        request_id=request.state.request_id,
    )


@router.get("/{job_id}", response_model=GenerationJobEnvelope, operation_id="getGenerationJob")
def get_generation_job(
    job_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> GenerationJobEnvelope:
    job = GenerationJobRepository(session, actor.organization_id).get(job_id)
    if job is None:
        raise ApiError(
            status_code=404,
            code="GENERATION_JOB_NOT_FOUND",
            message="The generation job was not found.",
        )
    if job.project_id is None:
        raise ApiError(
            status_code=404,
            code="GENERATION_JOB_NOT_FOUND",
            message="The generation job was not found.",
        )
    ProjectAccessService(session, actor).require(job.project_id, ProjectAction.VIEW)
    return GenerationJobEnvelope(
        data=GenerationJobRead.model_validate(job),
        request_id=request.state.request_id,
    )


@router.post(
    "/{job_id}/cancel",
    response_model=GenerationJobEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="cancelGenerationJob",
)
def cancel_generation_job(
    job_id: UUID,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> GenerationJobEnvelope:
    settings = cast(Settings, request.app.state.settings)
    with session.begin():
        job = GenerationJobService(
            session,
            actor=actor,
            idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
        ).request_cancel(
            job_id,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return GenerationJobEnvelope(data=job, request_id=request.state.request_id)


@router.get(
    "/{job_id}/events/stream",
    response_class=StreamingResponse,
    operation_id="streamGenerationJobEvents",
)
def stream_generation_job_events(
    job_id: UUID,
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
        job = GenerationJobRepository(session, actor.organization_id).get(job_id)
        if job is None or job.project_id is None:
            raise ApiError(
                status_code=404,
                code="GENERATION_JOB_NOT_FOUND",
                message="The generation job was not found.",
            )
        ProjectAccessService(session, actor).require(job.project_id, ProjectAction.VIEW)
        EventReplayRepository(session, actor.organization_id).replay(
            project_id=job.project_id,
            after_sequence=cursor,
            resource=("generation_job", job.id),
            limit=1,
        )
        project_id = job.project_id
    settings = cast(Settings, request.app.state.settings)
    return StreamingResponse(
        stream_events(
            factory,
            organization_id=actor.organization_id,
            project_id=project_id,
            after_sequence=cursor,
            resource=("generation_job", job_id),
            poll_seconds=settings.sse_poll_seconds,
            heartbeat_seconds=settings.sse_heartbeat_seconds,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
