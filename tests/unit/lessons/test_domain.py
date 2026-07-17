from __future__ import annotations

import pytest

from apps.api.lessons.domain import (
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
