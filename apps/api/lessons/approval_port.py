"""Lesson-owned completion coordinator with ORM-free upstream facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.domain import (
    ImpactSelector,
    StaleImpactDimension,
    StaleImpactSelection,
)
from apps.api.identity.context import ActorContext
from apps.api.lessons.division_runtime import (
    LessonDivisionDiff,
    build_approved_lesson_division,
    diff_lesson_divisions,
)
from apps.api.lessons.models import LessonUnit
from apps.api.lessons.repository import LessonRepository
from apps.api.lessons.service import LessonService
from apps.api.workflows.lesson_division_port import LessonDivisionWorkflowPort
from apps.api.workflows.lesson_fanout import (
    LessonFanoutTarget,
    LessonWorkflowFanoutService,
)


@dataclass(frozen=True, slots=True)
class LessonDivisionApprovalCommand:
    project_id: UUID
    artifact_version_id: UUID
    source_node_run_id: UUID
    producer_node_key: str
    approval_gate_node_key: str
    content_release_id: UUID
    workflow_definition_version_id: UUID
    content: dict[str, Any]
    previous_content: dict[str, Any] | None
    request_id: str | None


@dataclass(frozen=True, slots=True)
class LessonApprovalCompletionResult:
    stale_selection: StaleImpactSelection
    retained_selection: StaleImpactSelection
    lesson_count: int


@dataclass(frozen=True, slots=True)
class ApprovedLessonUnitFact:
    id: UUID
    lesson_key: str
    source_division_version_id: UUID


class LessonApprovalReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def current_lesson(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
    ) -> ApprovedLessonUnitFact | None:
        lesson = self._session.scalar(
            select(LessonUnit).where(
                LessonUnit.id == lesson_unit_id,
                LessonUnit.organization_id == self._actor.organization_id,
                LessonUnit.project_id == project_id,
                LessonUnit.status == "active",
                LessonUnit.deleted_at.is_(None),
            )
        )
        if lesson is None:
            return None
        return ApprovedLessonUnitFact(
            id=lesson.id,
            lesson_key=lesson.lesson_key,
            source_division_version_id=lesson.source_division_version_id,
        )


class LessonDivisionApprovalPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def apply(self, command: LessonDivisionApprovalCommand) -> LessonApprovalCompletionResult:
        workflow = LessonDivisionWorkflowPort(self._session, self._actor)
        run_id = workflow.require_source_run(
            source_node_run_id=command.source_node_run_id,
            artifact_version_id=command.artifact_version_id,
            expected_producer_node_key=command.producer_node_key,
            project_id=command.project_id,
            content_release_id=command.content_release_id,
            workflow_definition_version_id=command.workflow_definition_version_id,
        )
        diff = diff_lesson_divisions(command.previous_content, command.content)
        division = build_approved_lesson_division(
            command.artifact_version_id,
            command.content,
        )
        repository = LessonRepository(self._session, self._actor)
        existing = repository.list_for_project(
            command.project_id,
            include_archived=True,
            for_update=True,
        )
        desired_keys = {lesson.lesson_key for lesson in division.lessons}
        archived_ids = tuple(
            lesson.id for lesson in existing if lesson.lesson_key not in desired_keys
        )
        fanout = LessonWorkflowFanoutService(self._session, self._actor)
        fanout.lock_archivable(run_id, archived_ids)
        active = LessonService(self._session, self._actor).synchronize_declared_approval(
            command.project_id,
            division,
            request_id=command.request_id,
        )
        targets = tuple(
            LessonFanoutTarget(
                lesson_unit_id=lesson.id,
                branch_enabled={
                    config.branch_key: config.enabled
                    for config in repository.list_branch_configs(lesson.id, for_update=True)
                },
            )
            for lesson in active
        )
        fanout.synchronize_declared_approval(
            run_id,
            targets=targets,
            archived_lesson_unit_ids=archived_ids,
            request_id=command.request_id,
        )
        workflow.complete_gate(run_id, command.approval_gate_node_key)
        return LessonApprovalCompletionResult(
            stale_selection=_stale_selection(diff),
            retained_selection=_retained_selection(diff),
            lesson_count=len(active),
        )


def _stale_selection(diff: LessonDivisionDiff) -> StaleImpactSelection:
    return StaleImpactSelection.exact(
        (
            StaleImpactDimension(
                selector=ImpactSelector.LESSON_KEY,
                changed_keys=diff.changed_keys,
                archived_keys=diff.archived_keys,
            ),
        )
    )


def _retained_selection(diff: LessonDivisionDiff) -> StaleImpactSelection:
    return StaleImpactSelection.exact(
        (
            StaleImpactDimension(
                selector=ImpactSelector.LESSON_KEY,
                changed_keys=diff.unchanged_keys,
            ),
        )
    )
