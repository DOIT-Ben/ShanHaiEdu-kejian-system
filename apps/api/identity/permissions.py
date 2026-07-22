"""Project role matrix and tenant-safe authorization queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction, ProjectRole
from apps.api.identity.models import ProjectMember
from apps.api.projects.models import Project

ROLE_ACTIONS: dict[ProjectRole, frozenset[ProjectAction]] = {
    ProjectRole.OWNER: frozenset(ProjectAction),
    ProjectRole.EDITOR: frozenset({ProjectAction.VIEW, ProjectAction.EDIT, ProjectAction.GENERATE}),
    ProjectRole.REVIEWER: frozenset({ProjectAction.VIEW, ProjectAction.REVIEW}),
    ProjectRole.VIEWER: frozenset({ProjectAction.VIEW}),
}


def is_project_action_allowed(role: ProjectRole, action: ProjectAction) -> bool:
    return action in ROLE_ACTIONS[role]


class ProjectAccessService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require(
        self,
        project_id: UUID,
        action: ProjectAction,
        *,
        for_update: bool = False,
    ) -> Project:
        if self._actor.user_id is None or self._actor.is_system:
            raise self._not_found()
        statement = (
            select(Project, ProjectMember.role)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(
                Project.id == project_id,
                Project.organization_id == self._actor.organization_id,
                Project.deleted_at.is_(None),
                ProjectMember.user_id == self._actor.user_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=(Project, ProjectMember))
        row = self._session.execute(statement).one_or_none()
        if row is None:
            raise self._not_found()
        project, raw_role = row
        role = ProjectRole(raw_role)
        if not is_project_action_allowed(role, action):
            raise ApiError(
                status_code=403,
                code="PERMISSION_DENIED",
                message="The project role does not allow this action.",
            )
        return project

    def require_owner(self, project_id: UUID) -> Project:
        project = self.require(project_id, ProjectAction.REVIEW, for_update=True)
        role = self._session.scalar(
            select(ProjectMember.role).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == self._actor.user_id,
            )
        )
        if role != ProjectRole.OWNER.value:
            raise ApiError(
                status_code=403,
                code="PERMISSION_DENIED",
                message="Only a project owner can revoke an approval.",
            )
        return project

    def require_review_completion(
        self,
        project_id: UUID,
        *,
        for_update: bool,
    ) -> Project:
        """Authorize one declared approval effect without granting edit access."""

        if not self._actor.is_system:
            return self.require(project_id, ProjectAction.REVIEW, for_update=for_update)
        statement = select(Project).where(
            Project.id == project_id,
            Project.organization_id == self._actor.organization_id,
            Project.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        project = self._session.scalar(statement)
        if project is None:
            raise self._not_found()
        return project

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message="The project was not found.",
        )
