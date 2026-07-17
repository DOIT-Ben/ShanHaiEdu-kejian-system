"""Lesson application services and approved-division synchronization port."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.lessons.domain import (
    ApprovedLessonDivision,
    ApprovedLessonItem,
    BranchConfigurationChange,
    BranchKey,
    LessonCollectionEdit,
    LessonInvariantError,
    default_branch_states,
    ensure_branch_toggle_allowed,
)
from apps.api.lessons.models import LessonBranchConfig, LessonUnit
from apps.api.lessons.repository import LessonRepository
from apps.api.reliability.events import EventResource, EventWriter


class LessonService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = LessonRepository(session, actor)

    def synchronize_approved_division(
        self,
        project_id: UUID,
        division: ApprovedLessonDivision,
        *,
        request_id: str | None,
    ) -> list[LessonUnit]:
        project = ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.EDIT,
            for_update=True,
        )
        if project.lesson_division_version_id == division.version_id:
            return self._repository.list_for_project(project_id)

        existing = self._repository.list_for_project(
            project_id,
            include_archived=True,
            for_update=True,
        )
        original_positions = self._stage_existing_positions(existing)
        active = self._apply_approved_items(project_id, division, existing)
        archived = self._archive_missing(
            existing,
            active_ids={lesson.id for lesson in active},
            original_positions=original_positions,
            active_count=len(active),
        )

        project.lesson_division_version_id = division.version_id
        project.lock_version += 1
        project.updated_by = self._actor.principal_id
        project.updated_at = utc_now()
        self._session.flush()
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=project_id,
            event_type="lesson.collection.synchronized",
            resource=EventResource(type="lesson_collection", id=project_id),
            payload={
                "division_version_id": str(division.version_id),
                "active_count": len(active),
                "archived_count": len(archived),
            },
            request_id=request_id,
        )
        return active

    def update_collection(
        self,
        project_id: UUID,
        *,
        expected_version: int,
        items: tuple[LessonCollectionEdit, ...],
        request_id: str | None,
    ) -> list[LessonUnit]:
        project = ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.EDIT,
            for_update=True,
        )
        if project.lock_version != expected_version:
            raise ApiError(
                status_code=409,
                code="EDIT_CONFLICT",
                message="The lesson collection was changed by another editor.",
                details={"current_version": project.lock_version},
            )
        existing = self._repository.list_for_project(
            project_id,
            include_archived=True,
            for_update=True,
        )
        by_id = {lesson.id: lesson for lesson in existing}
        if any(item.id not in by_id for item in items):
            raise self._lesson_not_found()
        original_positions = self._stage_existing_positions(existing)
        active = self._apply_collection_edits(items, by_id)
        archived = self._archive_missing(
            existing,
            active_ids={lesson.id for lesson in active},
            original_positions=original_positions,
            active_count=len(active),
        )

        project.lock_version += 1
        project.updated_by = self._actor.principal_id
        project.updated_at = utc_now()
        self._session.flush()
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=project_id,
            event_type="lesson.collection.updated",
            resource=EventResource(type="lesson_collection", id=project_id),
            payload={
                "active_count": len(active),
                "archived_count": len(archived),
                "lock_version": project.lock_version,
            },
            request_id=request_id,
        )
        return active

    def update_branches(
        self,
        lesson_id: UUID,
        *,
        expected_version: int,
        changes: dict[BranchKey, BranchConfigurationChange],
        request_id: str | None,
    ) -> LessonUnit:
        visible = self._repository.get(lesson_id)
        if visible is None:
            raise self._lesson_not_found()
        ProjectAccessService(self._session, self._actor).require(
            visible.project_id,
            ProjectAction.EDIT,
            for_update=True,
        )
        lesson = self._repository.get(lesson_id, for_update=True)
        if lesson is None:
            raise self._lesson_not_found()
        if lesson.lock_version != expected_version:
            raise ApiError(
                status_code=409,
                code="EDIT_CONFLICT",
                message="The lesson branch configuration was changed by another editor.",
                details={"current_version": lesson.lock_version},
            )
        configs = {
            BranchKey(config.branch_key): config
            for config in self._repository.list_branch_configs(lesson_id, for_update=True)
        }
        self._apply_branch_changes(configs, changes)
        lesson.lock_version += 1
        lesson.updated_by = self._actor.principal_id
        lesson.updated_at = utc_now()
        self._session.flush()
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=lesson.project_id,
            event_type="lesson.branches.updated",
            resource=EventResource(type="lesson", id=lesson.id),
            payload={
                "lesson_id": str(lesson.id),
                "lock_version": lesson.lock_version,
                "branches": {
                    branch_key.value: change.enabled for branch_key, change in changes.items()
                },
            },
            request_id=request_id,
        )
        return lesson

    def _apply_branch_changes(
        self,
        configs: dict[BranchKey, LessonBranchConfig],
        changes: dict[BranchKey, BranchConfigurationChange],
    ) -> None:
        for branch_key, change in changes.items():
            try:
                ensure_branch_toggle_allowed(branch_key, enabled=change.enabled)
            except LessonInvariantError as exc:
                raise ApiError(
                    status_code=422,
                    code="LESSON_PLAN_REQUIRED",
                    message="The lesson plan branch is required and cannot be disabled.",
                ) from exc
            config = configs[branch_key]
            config.enabled = change.enabled
            config.settings_json = change.settings
            config.updated_by = self._actor.principal_id
            config.updated_at = utc_now()
            config.lock_version += 1

    def _stage_existing_positions(self, lessons: list[LessonUnit]) -> dict[UUID, int]:
        original_positions = {lesson.id: lesson.position for lesson in lessons}
        temporary_start = max((lesson.position for lesson in lessons), default=0) + len(lessons) + 1
        for offset, lesson in enumerate(lessons):
            lesson.position = temporary_start + offset
        if lessons:
            self._session.flush()
        return original_positions

    def _apply_approved_items(
        self,
        project_id: UUID,
        division: ApprovedLessonDivision,
        existing: list[LessonUnit],
    ) -> list[LessonUnit]:
        by_key = {lesson.lesson_key: lesson for lesson in existing}
        active: list[LessonUnit] = []
        for item in sorted(division.lessons, key=lambda value: value.position):
            lesson = by_key.get(item.lesson_key)
            if lesson is None:
                lesson = self._new_lesson(project_id, division.version_id, item)
                self._session.add(lesson)
                self._session.flush()
                self._add_default_branches(lesson.id)
            else:
                self._update_from_approved_item(lesson, division.version_id, item)
            active.append(lesson)
        return active

    def _apply_collection_edits(
        self,
        items: tuple[LessonCollectionEdit, ...],
        by_id: dict[UUID, LessonUnit],
    ) -> list[LessonUnit]:
        active: list[LessonUnit] = []
        for item in sorted(items, key=lambda value: value.position):
            lesson = by_id[item.id]
            lesson.position = item.position
            lesson.title = item.title
            lesson.scope_summary = item.scope_summary
            lesson.objective_summary = item.objective_summary
            lesson.estimated_minutes = item.estimated_minutes
            lesson.status = "active"
            self._touch_lesson(lesson)
            active.append(lesson)
        return active

    def _archive_missing(
        self,
        lessons: list[LessonUnit],
        *,
        active_ids: set[UUID],
        original_positions: dict[UUID, int],
        active_count: int,
    ) -> list[LessonUnit]:
        archived = sorted(
            (lesson for lesson in lessons if lesson.id not in active_ids),
            key=lambda lesson: original_positions[lesson.id],
        )
        for position, lesson in enumerate(archived, start=active_count + 1):
            lesson.position = position
            lesson.status = "archived"
            self._touch_lesson(lesson)
        return archived

    def _update_from_approved_item(
        self,
        lesson: LessonUnit,
        version_id: UUID,
        item: ApprovedLessonItem,
    ) -> None:
        lesson.position = item.position
        lesson.title = item.title
        lesson.scope_summary = item.scope_summary
        lesson.objective_summary = item.objective_summary
        lesson.estimated_minutes = item.estimated_minutes
        lesson.source_division_version_id = version_id
        lesson.status = "active"
        self._touch_lesson(lesson)

    def _touch_lesson(self, lesson: LessonUnit) -> None:
        lesson.lock_version += 1
        lesson.updated_by = self._actor.principal_id
        lesson.updated_at = utc_now()

    def _new_lesson(
        self,
        project_id: UUID,
        version_id: UUID,
        item: ApprovedLessonItem,
    ) -> LessonUnit:
        return LessonUnit(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=project_id,
            lesson_key=item.lesson_key,
            position=item.position,
            title=item.title,
            scope_summary=item.scope_summary,
            objective_summary=item.objective_summary,
            estimated_minutes=item.estimated_minutes,
            source_division_version_id=version_id,
            status="active",
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )

    def _add_default_branches(self, lesson_id: UUID) -> None:
        for branch_key, enabled in default_branch_states().items():
            self._session.add(
                LessonBranchConfig(
                    id=new_uuid7(),
                    lesson_unit_id=lesson_id,
                    branch_key=branch_key.value,
                    enabled=enabled,
                    settings_json={},
                    created_by=self._actor.principal_id,
                    updated_by=self._actor.principal_id,
                )
            )
        self._session.flush()

    @staticmethod
    def _lesson_not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="LESSON_NOT_FOUND",
            message="The lesson was not found.",
        )
