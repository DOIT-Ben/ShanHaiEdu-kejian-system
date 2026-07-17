"""Read-only project workflow aggregate endpoint."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from apps.api.dependencies import get_session
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService
from apps.api.lessons.repository import LessonRepository
from apps.api.projects.schemas import ProjectRead
from apps.api.workflows.repository import WorkflowRuntimeRepository
from apps.api.workflows.schemas import (
    NodeRunRead,
    WorkflowAggregateData,
    WorkflowEnvelope,
    WorkflowRunRead,
)

router = APIRouter(tags=["workflows"])


@router.get(
    "/api/v2/projects/{project_id}/workflow",
    response_model=WorkflowEnvelope,
    operation_id="getProjectWorkflow",
)
def get_project_workflow(
    project_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> WorkflowEnvelope:
    project = ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    workflow_repository = WorkflowRuntimeRepository(session, actor)
    workflow_run = workflow_repository.latest_for_project(project_id)
    node_runs = workflow_repository.list_nodes(workflow_run.id) if workflow_run else []
    lessons = LessonRepository(session, actor).list_for_project(project_id)
    return WorkflowEnvelope(
        data=WorkflowAggregateData(
            project=ProjectRead.model_validate(project),
            workflow_run=(
                WorkflowRunRead.model_validate(workflow_run) if workflow_run is not None else None
            ),
            lessons=[
                {
                    "id": str(lesson.id),
                    "lesson_key": lesson.lesson_key,
                    "position": lesson.position,
                    "title": lesson.title,
                    "status": lesson.status,
                }
                for lesson in lessons
            ],
            node_runs=[
                NodeRunRead.model_validate(
                    {
                        "id": node.id,
                        "workflow_run_id": node.workflow_run_id,
                        "branch_run_id": node.branch_run_id,
                        "node_key": node.node_key,
                        "run_no": node.run_no,
                        "status": node.status,
                        "stale_reason": node.stale_reason_json,
                        "started_at": node.started_at,
                        "finished_at": node.finished_at,
                    }
                )
                for node in node_runs
            ],
        ),
        request_id=request.state.request_id,
    )
