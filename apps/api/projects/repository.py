"""Tenant-scoped project repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.api.content_runtime.registry import RuntimeDefaults
from apps.api.content_runtime.service import require_published_runtime, resolve_runtime_defaults
from apps.api.database import utc_now
from apps.api.identity.context import ActorContext
from apps.api.identity.models import ProjectMember
from apps.api.ids import new_uuid7
from apps.api.projects.models import AutomationPolicy, Project
from apps.api.projects.policy_schemas import initial_policy_values
from apps.api.projects.schemas import CreateProjectRequest


class ProjectRepository:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        defaults: RuntimeDefaults | None = None,
    ) -> None:
        self._session = session
        self._actor = actor
        self._defaults = defaults

    def create(self, request: CreateProjectRequest) -> Project:
        if self._actor.user_id is None or self._actor.is_system:
            raise ValueError("project creation requires a user actor")
        defaults = self._defaults or resolve_runtime_defaults(self._session)
        require_published_runtime(self._session, defaults)
        project_id = new_uuid7()
        project = Project(
            id=project_id,
            organization_id=self._actor.organization_id,
            project_no=f"PRJ-{project_id.hex[-12:].upper()}",
            title=request.title,
            subject="primary_math",
            school_stage="primary",
            grade=request.grade,
            textbook_edition=request.textbook_edition,
            knowledge_point=request.knowledge_point,
            default_language="zh-CN",
            status="draft",
            legacy_automation_mode=(
                request.automation_mode
                or ("automatic" if request.execution_mode == "automatic" else "assisted")
            ),
            owner_principal_id=self._actor.principal_id,
            content_release_id=defaults.content_release_id,
            workflow_definition_version_id=defaults.workflow_definition_version_id,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(project)
        self._session.flush()
        membership = ProjectMember(
            id=new_uuid7(),
            project_id=project_id,
            user_id=self._actor.user_id,
            role="owner",
            created_at=utc_now(),
        )
        self._session.add(membership)
        policy_mode, node_rules = initial_policy_values(
            execution_mode=request.execution_mode,
            automation_mode=request.automation_mode,
        )
        self._session.add(
            AutomationPolicy(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                project_id=project.id,
                workflow_definition_version_id=project.workflow_definition_version_id,
                mode=policy_mode,
                node_rules_json=node_rules,
                policy_version=1,
                created_at=utc_now(),
                created_by=self._actor.principal_id,
            )
        )
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
        statement = select(Project).where(
            Project.organization_id == self._actor.organization_id,
            Project.deleted_at.is_(None),
        )
        if self._actor.user_id is not None and not self._actor.is_system:
            statement = statement.join(
                ProjectMember,
                (ProjectMember.project_id == Project.id)
                & (ProjectMember.user_id == self._actor.user_id),
            )
        return statement
