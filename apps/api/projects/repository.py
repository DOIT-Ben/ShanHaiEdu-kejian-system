"""Tenant-scoped project repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.api.ids import new_uuid7
from apps.api.projects.models import Project
from apps.api.projects.schemas import CreateProjectRequest


class ProjectRepository:
    def __init__(self, session: Session, organization_id: UUID, principal_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id
        self._principal_id = principal_id

    def create(self, request: CreateProjectRequest) -> Project:
        project_id = new_uuid7()
        project = Project(
            id=project_id,
            organization_id=self._organization_id,
            project_no=f"PRJ-{project_id.hex[-12:].upper()}",
            title=request.title,
            subject="primary_math",
            school_stage="primary",
            grade=request.grade,
            textbook_edition=request.textbook_edition,
            knowledge_point=request.knowledge_point,
            default_language="zh-CN",
            status="draft",
            automation_mode=request.automation_mode,
            owner_principal_id=self._principal_id,
            created_by=self._principal_id,
            updated_by=self._principal_id,
        )
        self._session.add(project)
        self._session.flush()
        return project

    def get(self, project_id: UUID, *, for_update: bool = False) -> Project | None:
        statement = self._active_projects().where(Project.id == project_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def list_page(self, *, cursor: UUID | None, limit: int) -> tuple[list[Project], str | None]:
        statement = self._active_projects().order_by(Project.id.desc()).limit(limit + 1)
        if cursor is not None:
            statement = statement.where(Project.id < cursor)
        projects = list(self._session.scalars(statement))
        has_more = len(projects) > limit
        page = projects[:limit]
        next_cursor = str(page[-1].id) if has_more and page else None
        return page, next_cursor

    def _active_projects(self) -> Select[tuple[Project]]:
        return select(Project).where(
            Project.organization_id == self._organization_id,
            Project.deleted_at.is_(None),
        )
