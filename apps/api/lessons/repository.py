"""Tenant-scoped lesson persistence queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.identity.models import ProjectMember
from apps.api.lessons.models import LessonBranchConfig, LessonUnit


class LessonRepository:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def list_for_project(
        self,
        project_id: UUID,
        *,
        include_archived: bool = False,
        for_update: bool = False,
    ) -> list[LessonUnit]:
        statement = self._visible_lessons().where(LessonUnit.project_id == project_id)
        if not include_archived:
            statement = statement.where(LessonUnit.status == "active")
        statement = statement.order_by(LessonUnit.position, LessonUnit.id)
        if for_update:
            statement = statement.with_for_update(of=LessonUnit)
        return list(self._session.scalars(statement))

    def get(self, lesson_id: UUID, *, for_update: bool = False) -> LessonUnit | None:
        statement = self._visible_lessons().where(LessonUnit.id == lesson_id)
        if for_update:
            statement = statement.with_for_update(of=LessonUnit)
        return self._session.scalar(statement)

    def list_branch_configs(
        self,
        lesson_id: UUID,
        *,
        for_update: bool = False,
    ) -> list[LessonBranchConfig]:
        statement = (
            select(LessonBranchConfig)
            .join(LessonUnit, LessonUnit.id == LessonBranchConfig.lesson_unit_id)
            .where(
                LessonBranchConfig.lesson_unit_id == lesson_id,
                LessonBranchConfig.deleted_at.is_(None),
                LessonUnit.organization_id == self._actor.organization_id,
                LessonUnit.deleted_at.is_(None),
            )
            .order_by(LessonBranchConfig.branch_key)
        )
        if self._actor.user_id is not None and not self._actor.is_system:
            statement = statement.join(
                ProjectMember,
                (ProjectMember.project_id == LessonUnit.project_id)
                & (ProjectMember.user_id == self._actor.user_id),
            )
        if for_update:
            statement = statement.with_for_update(of=LessonBranchConfig)
        return list(self._session.scalars(statement))

    def _visible_lessons(self) -> Select[tuple[LessonUnit]]:
        statement = select(LessonUnit).where(
            LessonUnit.organization_id == self._actor.organization_id,
            LessonUnit.deleted_at.is_(None),
        )
        if self._actor.user_id is not None and not self._actor.is_system:
            statement = statement.join(
                ProjectMember,
                (ProjectMember.project_id == LessonUnit.project_id)
                & (ProjectMember.user_id == self._actor.user_id),
            )
        return statement
