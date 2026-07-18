"""Current project read projection backed by versioned automation policy."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.projects.models import AutomationPolicy, Project
from apps.api.projects.schemas import ProjectRead


class ProjectReadService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def present(self, project: Project) -> ProjectRead:
        return self.present_many((project,))[0]

    def present_many(self, projects: Sequence[Project]) -> list[ProjectRead]:
        if not projects:
            return []
        modes = self._current_modes([project.id for project in projects])
        return [self._present(project, modes[project.id]) for project in projects]

    def _current_modes(self, project_ids: list[UUID]) -> dict[UUID, str]:
        latest = (
            select(
                AutomationPolicy.project_id,
                func.max(AutomationPolicy.policy_version).label("policy_version"),
            )
            .where(
                AutomationPolicy.organization_id == self._actor.organization_id,
                AutomationPolicy.project_id.in_(project_ids),
            )
            .group_by(AutomationPolicy.project_id)
            .subquery()
        )
        rows = self._session.execute(
            select(AutomationPolicy.project_id, AutomationPolicy.mode)
            .join(
                latest,
                and_(
                    latest.c.project_id == AutomationPolicy.project_id,
                    latest.c.policy_version == AutomationPolicy.policy_version,
                ),
            )
            .where(AutomationPolicy.organization_id == self._actor.organization_id)
        )
        modes = {project_id: mode for project_id, mode in rows}
        missing = [project_id for project_id in project_ids if project_id not in modes]
        if missing:
            raise ApiError(
                status_code=409,
                code="AUTOMATION_POLICY_MISSING",
                message="The project automation policy has not been initialized.",
                details={"project_ids": [str(project_id) for project_id in missing]},
            )
        return modes

    @staticmethod
    def _present(project: Project, execution_mode: str) -> ProjectRead:
        return ProjectRead.model_validate(
            {
                "id": project.id,
                "title": project.title,
                "subject": project.subject,
                "grade": project.grade,
                "textbook_edition": project.textbook_edition,
                "knowledge_point": project.knowledge_point,
                "status": project.status,
                "execution_mode": execution_mode,
                "content_release_id": project.content_release_id,
                "workflow_definition_version_id": project.workflow_definition_version_id,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
            }
        )
