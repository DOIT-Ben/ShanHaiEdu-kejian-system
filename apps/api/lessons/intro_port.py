"""Lesson-owned access facts for Intro HTTP operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.lessons.models import LessonUnit


@dataclass(frozen=True, slots=True)
class IntroLessonFact:
    id: UUID
    project_id: UUID
    lesson_key: str


class IntroLessonReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require_view(self, lesson_unit_id: UUID) -> IntroLessonFact:
        lesson = self._session.scalar(
            select(LessonUnit).where(
                LessonUnit.id == lesson_unit_id,
                LessonUnit.organization_id == self._actor.organization_id,
                LessonUnit.status == "active",
                LessonUnit.deleted_at.is_(None),
            )
        )
        if lesson is None:
            raise ApiError(
                status_code=404,
                code="LESSON_NOT_FOUND",
                message="The lesson was not found.",
            )
        ProjectAccessService(self._session, self._actor).require(
            lesson.project_id,
            ProjectAction.VIEW,
        )
        return IntroLessonFact(
            id=lesson.id,
            project_id=lesson.project_id,
            lesson_key=lesson.lesson_key,
        )
