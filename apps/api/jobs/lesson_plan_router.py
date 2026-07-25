"""Exact lesson-plan GenerationJob recovery query."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from apps.api.dependencies import get_session
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService
from apps.api.jobs.repository import GenerationJobRepository
from apps.api.jobs.schemas import (
    GenerationJobListData,
    GenerationJobListEnvelope,
    GenerationJobRead,
)

router = APIRouter(tags=["generation-jobs"])


@router.get(
    "/api/v2/projects/{project_id}/lessons/{lesson_id}/lesson-plan/generation-jobs",
    response_model=GenerationJobListEnvelope,
    operation_id="listLessonPlanGenerationJobs",
)
def list_lesson_plan_generation_jobs(
    project_id: UUID,
    lesson_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> GenerationJobListEnvelope:
    ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    jobs = GenerationJobRepository(session, actor.organization_id).list_lesson_plan_jobs(
        project_id,
        lesson_id,
    )
    return GenerationJobListEnvelope(
        data=GenerationJobListData(items=[GenerationJobRead.model_validate(job) for job in jobs]),
        request_id=request.state.request_id,
    )
