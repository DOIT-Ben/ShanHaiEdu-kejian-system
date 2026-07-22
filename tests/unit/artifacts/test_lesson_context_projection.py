from __future__ import annotations

import pytest

from apps.api.artifacts.lesson_context_projection import (
    LessonContextProjectionError,
    project_artifact_context,
)


def _lesson(key: str) -> dict[str, object]:
    return {
        "lesson_unit_key": key,
        "title": f"Title {key}",
        "duration_minutes": 40,
        "material_scope": f"Scope {key}",
        "core_learning_outcome": f"Outcome {key}",
        "evidence_refs": [f"EV-{key}"],
        "must_not_preteach": [f"Later {key}"],
    }


def test_lesson_division_context_exposes_only_the_target_lesson() -> None:
    first = _lesson("LESSON-001")
    second = _lesson("LESSON-002")

    projected = project_artifact_context(
        source="lesson_division.approved_version",
        lesson_key="LESSON-002",
        content={
            "division_key": "DIVISION-001",
            "lesson_count": 2,
            "lesson_units": [first, second],
        },
    )

    assert projected == {
        "division_key": "DIVISION-001",
        "lesson_unit": second,
    }
    assert "lesson_units" not in projected


@pytest.mark.parametrize(
    "lesson_units",
    [
        [_lesson("LESSON-001")],
        [_lesson("LESSON-002"), _lesson("LESSON-002")],
    ],
)
def test_lesson_division_context_requires_one_exact_target(
    lesson_units: list[dict[str, object]],
) -> None:
    with pytest.raises(LessonContextProjectionError) as caught:
        project_artifact_context(
            source="lesson_division.approved_version",
            lesson_key="LESSON-002",
            content={
                "division_key": "DIVISION-001",
                "lesson_count": len(lesson_units),
                "lesson_units": lesson_units,
            },
        )

    assert caught.value.code == "NODE_EXECUTION_LESSON_SCOPE_INVALID"
