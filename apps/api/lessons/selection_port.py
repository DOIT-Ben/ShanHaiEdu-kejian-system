"""Lesson-owned locking facts used by Intro selection commands."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.lessons.models import LessonUnit


@dataclass(frozen=True, slots=True)
class SelectableLessonFact:
    id: UUID
    project_id: UUID
    lesson_key: str


class LessonSelectionReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require(self, *, project_id: UUID, lesson_unit_id: UUID) -> SelectableLessonFact:
        lesson = self._session.scalar(
            select(LessonUnit)
            .where(
                LessonUnit.id == lesson_unit_id,
                LessonUnit.organization_id == self._actor.organization_id,
                LessonUnit.project_id == project_id,
                LessonUnit.status == "active",
                LessonUnit.deleted_at.is_(None),
            )
            .with_for_update(of=LessonUnit)
        )
        if lesson is None:
            raise ApiError(
                status_code=409,
                code="INTRO_SELECTION_INVALID",
                message="The target lesson is not active in this project.",
            )
        return SelectableLessonFact(
            id=lesson.id,
            project_id=lesson.project_id,
            lesson_key=lesson.lesson_key,
        )
