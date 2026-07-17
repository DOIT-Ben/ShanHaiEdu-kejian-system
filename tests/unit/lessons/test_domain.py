from __future__ import annotations

from uuid import UUID

import pytest

from apps.api.lessons.domain import (
    ApprovedLessonDivision,
    ApprovedLessonItem,
    BranchKey,
    LessonInvariantError,
    default_branch_states,
    ensure_branch_toggle_allowed,
    workflow_status_for_branch,
)


def test_new_lesson_has_exactly_four_default_branch_states() -> None:
    assert default_branch_states() == {
        BranchKey.LESSON_PLAN: True,
        BranchKey.INTRO_OPTIONS: True,
        BranchKey.PPT: False,
        BranchKey.VIDEO: False,
    }


def test_lesson_plan_branch_cannot_be_disabled() -> None:
    with pytest.raises(LessonInvariantError, match="lesson_plan"):
        ensure_branch_toggle_allowed(BranchKey.LESSON_PLAN, enabled=False)


def test_disabled_branch_never_maps_to_skipped_workflow_status() -> None:
    assert workflow_status_for_branch(enabled=False) == "disabled"
    assert workflow_status_for_branch(enabled=False) != "skipped"


def test_approved_division_rejects_duplicate_or_non_contiguous_positions() -> None:
    with pytest.raises(LessonInvariantError, match="positions"):
        ApprovedLessonDivision(
            version_id=UUID("01950000-0000-7000-8000-000000000001"),
            lessons=(
                ApprovedLessonItem("lesson-01", 1, "First", "Scope", "Objective", 40),
                ApprovedLessonItem("lesson-02", 3, "Second", "Scope", "Objective", 40),
            ),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("lesson_key", "x" * 81, "lesson_key"),
        ("title", "x" * 256, "title"),
        ("scope_summary", " ", "scope_summary"),
        ("objective_summary", " ", "objective_summary"),
    ),
)
def test_approved_lesson_item_rejects_invalid_text_fields(
    field: str,
    value: str,
    message: str,
) -> None:
    values = {
        "lesson_key": "lesson-01",
        "position": 1,
        "title": "First",
        "scope_summary": "Scope",
        "objective_summary": "Objective",
        "estimated_minutes": 40,
    }
    values[field] = value
    with pytest.raises(LessonInvariantError, match=message):
        ApprovedLessonItem(**values)
