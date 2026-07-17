"""Stable lesson and branch business rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID


class BranchKey(StrEnum):
    LESSON_PLAN = "lesson_plan"
    INTRO_OPTIONS = "intro_options"
    PPT = "ppt"
    VIDEO = "video"


class LessonInvariantError(ValueError):
    """Raised when a requested lesson state violates product semantics."""


@dataclass(frozen=True, slots=True)
class ApprovedLessonItem:
    lesson_key: str
    position: int
    title: str
    scope_summary: str
    objective_summary: str
    estimated_minutes: int | None = None

    def __post_init__(self) -> None:
        if not self.lesson_key.strip():
            raise LessonInvariantError("lesson_key cannot be empty")
        if len(self.lesson_key) > 80:
            raise LessonInvariantError("lesson_key cannot exceed 80 characters")
        if self.position <= 0:
            raise LessonInvariantError("lesson position must be greater than zero")
        if not self.title.strip():
            raise LessonInvariantError("lesson title cannot be empty")
        if len(self.title) > 255:
            raise LessonInvariantError("lesson title cannot exceed 255 characters")
        if not self.scope_summary.strip():
            raise LessonInvariantError("scope_summary cannot be empty")
        if not self.objective_summary.strip():
            raise LessonInvariantError("objective_summary cannot be empty")
        if self.estimated_minutes is not None and self.estimated_minutes <= 0:
            raise LessonInvariantError("estimated_minutes must be greater than zero")


@dataclass(frozen=True, slots=True)
class ApprovedLessonDivision:
    version_id: UUID
    lessons: tuple[ApprovedLessonItem, ...]

    def __post_init__(self) -> None:
        if not self.lessons:
            raise LessonInvariantError("an approved division must contain at least one lesson")
        keys = [lesson.lesson_key for lesson in self.lessons]
        positions = [lesson.position for lesson in self.lessons]
        if len(keys) != len(set(keys)):
            raise LessonInvariantError("lesson_key values must be unique")
        if len(positions) != len(set(positions)):
            raise LessonInvariantError("lesson positions must be unique")
        if sorted(positions) != list(range(1, len(positions) + 1)):
            raise LessonInvariantError("lesson positions must be contiguous starting at one")


@dataclass(frozen=True, slots=True)
class BranchConfigurationChange:
    enabled: bool
    settings: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LessonCollectionEdit:
    id: UUID
    position: int
    title: str
    scope_summary: str
    objective_summary: str
    estimated_minutes: int | None

    def __post_init__(self) -> None:
        if self.position <= 0:
            raise LessonInvariantError("lesson position must be greater than zero")
        if not self.title.strip() or len(self.title) > 255:
            raise LessonInvariantError("lesson title must contain at most 255 characters")
        if not self.scope_summary.strip() or not self.objective_summary.strip():
            raise LessonInvariantError("lesson summaries cannot be empty")
        if self.estimated_minutes is not None and self.estimated_minutes <= 0:
            raise LessonInvariantError("estimated_minutes must be greater than zero")


def default_branch_states() -> dict[BranchKey, bool]:
    return {
        BranchKey.LESSON_PLAN: True,
        BranchKey.INTRO_OPTIONS: True,
        BranchKey.PPT: False,
        BranchKey.VIDEO: False,
    }


def ensure_branch_toggle_allowed(branch_key: BranchKey, *, enabled: bool) -> None:
    if branch_key is BranchKey.LESSON_PLAN and not enabled:
        raise LessonInvariantError("lesson_plan is required and cannot be disabled")


def workflow_status_for_branch(*, enabled: bool) -> Literal["disabled", "not_ready"]:
    return "not_ready" if enabled else "disabled"
