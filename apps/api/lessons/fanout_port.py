"""Lesson-owned scope validation for workflow fanout writes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.lessons.models import LessonUnit


class LessonFanoutScopeError(ValueError):
    """Raised when workflow fanout targets do not match lesson-owned facts."""


class SqlAlchemyLessonFanoutScopePort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require_scope(
        self,
        project_id: UUID,
        *,
        active_ids: tuple[UUID, ...],
        archived_ids: tuple[UUID, ...],
    ) -> None:
        expected = set((*active_ids, *archived_ids))
        if not expected:
            return
        lessons = list(
            self._session.scalars(
                select(LessonUnit)
                .where(
                    LessonUnit.id.in_(expected),
                    LessonUnit.organization_id == self._actor.organization_id,
                    LessonUnit.project_id == project_id,
                    LessonUnit.deleted_at.is_(None),
                )
                .order_by(LessonUnit.id)
                .with_for_update(of=LessonUnit)
            )
        )
        by_id = {lesson.id: lesson for lesson in lessons}
        if set(by_id) != expected:
            raise LessonFanoutScopeError(
                "lesson fanout contains a lesson outside the workflow project"
            )
        if any(by_id[lesson_id].status != "active" for lesson_id in active_ids):
            raise LessonFanoutScopeError("lesson fanout target is not active")
        if any(by_id[lesson_id].status != "archived" for lesson_id in archived_ids):
            raise LessonFanoutScopeError("lesson fanout archive target is not archived")
