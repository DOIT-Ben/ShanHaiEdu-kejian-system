"""Application composition for the public Intro options query."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.intro_option_query_port import (
    IntroOptionQueryReader,
    IntroOptionVersionFact,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.intro_options.schemas import (
    IntroOptionsRead,
    IntroOptionVersionRead,
    IntroSelectionPublicRead,
)
from apps.api.intro_selections.schemas import IntroSelectionRead
from apps.api.intro_selections.service import IntroSelectionService
from apps.api.lessons.intro_port import IntroLessonReader


class IntroOptionsQueryService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def get(self, lesson_unit_id: UUID) -> IntroOptionsRead:
        lesson = IntroLessonReader(self._session, self._actor).require_view(lesson_unit_id)
        artifact = IntroOptionQueryReader(self._session, self._actor).for_lesson(
            project_id=lesson.project_id,
            lesson_unit_id=lesson.id,
            lesson_key=lesson.lesson_key,
        )
        if artifact is None:
            raise ApiError(
                status_code=404,
                code="INTRO_OPTIONS_NOT_FOUND",
                message="The Intro option set was not found.",
            )
        selection = IntroSelectionService(self._session, self._actor).current(
            project_id=lesson.project_id,
            lesson_unit_id=lesson.id,
        )
        return IntroOptionsRead(
            artifact_id=artifact.artifact_id,
            current_approved_version_id=artifact.current_approved_version_id,
            display_version=_version(artifact.display_version),
            pending_version=_version(artifact.pending_version),
            current_selection=to_public_selection(selection) if selection is not None else None,
        )


def _version(fact: IntroOptionVersionFact | None) -> IntroOptionVersionRead | None:
    if fact is None:
        return None
    return IntroOptionVersionRead.model_validate(
        {
            "artifact_version_id": fact.artifact_version_id,
            "version_no": fact.version_no,
            "approval_status": fact.approval_status,
            "stale": fact.stale,
            "selectable": fact.selectable,
            "option_set": fact.option_set,
        }
    )


def to_public_selection(selection: IntroSelectionRead) -> IntroSelectionPublicRead:
    return IntroSelectionPublicRead(
        selection_id=selection.id,
        artifact_version_id=selection.artifact_version_id,
        option_key=selection.option_key,
        selection_method=selection.selection_method,
        snapshot=selection.snapshot,
        reason=selection.reason,
        active=selection.active,
        consumable=selection.consumable,
        unconsumable_reason=selection.unconsumable_reason,
        selected_at=selection.selected_at,
        deactivated_at=selection.deactivated_at,
    )
