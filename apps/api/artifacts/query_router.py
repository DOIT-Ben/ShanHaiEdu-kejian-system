"""Project-scoped artifact query endpoint."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.router import serialize_artifact
from apps.api.artifacts.schemas import ArtifactListData, ArtifactListEnvelope, ArtifactPageMeta
from apps.api.dependencies import get_session
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService
from apps.api.pagination import parse_uuid_page_cursor

router = APIRouter(tags=["artifacts"])


@router.get(
    "/api/v2/projects/{project_id}/artifacts",
    response_model=ArtifactListEnvelope,
    operation_id="listProjectArtifacts",
)
def list_project_artifacts(
    project_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
    lesson_id: Annotated[UUID | None, Query()] = None,
    artifact_type: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    page_cursor: Annotated[str | None, Query(alias="page[cursor]")] = None,
    page_limit: Annotated[int, Query(alias="page[limit]", ge=1, le=100)] = 20,
) -> ArtifactListEnvelope:
    ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    artifacts, next_cursor = ArtifactRepository(session, actor).list_page(
        project_id,
        cursor=parse_uuid_page_cursor(page_cursor),
        limit=page_limit,
        lesson_unit_id=lesson_id,
        artifact_type=artifact_type,
    )
    return ArtifactListEnvelope(
        data=ArtifactListData(
            items=[serialize_artifact(session, actor, artifact) for artifact in artifacts]
        ),
        meta=ArtifactPageMeta(next_cursor=next_cursor),
        request_id=request.state.request_id,
    )
