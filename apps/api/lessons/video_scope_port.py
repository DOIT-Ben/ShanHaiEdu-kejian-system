"""Lesson-owned scope facts for the video golden slice."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.lessons.models import LessonBranchConfig, LessonUnit


@dataclass(frozen=True, slots=True)
class VideoLessonScope:
    lesson_unit_id: UUID
    project_id: UUID
    position: int


class VideoLessonScopeReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def active(
        self, project_id: UUID, lesson_id: UUID, *, for_update: bool = False
    ) -> VideoLessonScope | None:
        statement = (
            select(LessonUnit)
            .join(LessonBranchConfig, LessonBranchConfig.lesson_unit_id == LessonUnit.id)
            .where(
                LessonUnit.id == lesson_id,
                LessonUnit.project_id == project_id,
                LessonUnit.organization_id == self._actor.organization_id,
                LessonUnit.status == "active",
                LessonUnit.deleted_at.is_(None),
                LessonBranchConfig.branch_key == "video",
                LessonBranchConfig.enabled.is_(True),
                LessonBranchConfig.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=LessonUnit)
        lesson = self._session.scalar(statement)
        if lesson is None:
            return None
        return VideoLessonScope(
            lesson_unit_id=lesson.id,
            project_id=lesson.project_id,
            position=lesson.position,
        )
