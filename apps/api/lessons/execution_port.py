"""Lesson facts exposed to workflow execution without leaking ORM models."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.lessons.models import LessonUnit


@dataclass(frozen=True, slots=True)
class LessonExecutionFacts:
    lesson_unit_id: UUID
    project_id: UUID
    lesson_key: str


class SqlAlchemyLessonExecutionPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require_active(
        self,
        lesson_unit_id: UUID,
        *,
        project_id: UUID,
    ) -> LessonExecutionFacts:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.GENERATE,
        )
        lesson = self._session.scalar(
            select(LessonUnit).where(
                LessonUnit.id == lesson_unit_id,
                LessonUnit.organization_id == self._actor.organization_id,
                LessonUnit.project_id == project_id,
                LessonUnit.deleted_at.is_(None),
                LessonUnit.status == "active",
            )
        )
        if lesson is None:
            raise ValueError("the lesson unit is not visible or active")
        return LessonExecutionFacts(
            lesson_unit_id=lesson.id,
            project_id=lesson.project_id,
            lesson_key=lesson.lesson_key,
        )
