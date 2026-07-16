"""Stage-zero project HTTP endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.orm import Session

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
    _idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    session: Annotated[Session, Depends(get_session)],
) -> ProjectEnvelope:
    with session.begin():
        project = repository(session).create(payload)
    return ProjectEnvelope(
        data=ProjectRead.model_validate(project),
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
