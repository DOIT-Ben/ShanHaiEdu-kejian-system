from __future__ import annotations

from copy import deepcopy
from uuid import UUID

import pytest

from apps.api.artifact_quality.contracts import QualityValidationContext
from apps.api.lessons.division_runtime import (
    LESSON_DIVISION_COVERAGE_REF,
    LESSON_DIVISION_SCHEMA_REF,
    LessonDivisionCoverageValidator,
    LessonDivisionSchemaValidator,
    build_approved_lesson_division,
    diff_lesson_divisions,
)

VERSION_ID = UUID("10000000-0000-4000-8000-000000000125")


def lesson_unit(key: str, position: int) -> dict[str, object]:
    return {
        "lesson_unit_key": key,
        "position": position,
        "title": f"Lesson {position}",
        "lesson_type": "new_learning",
        "duration_minutes": 40,
        "core_learning_outcome": f"Observable outcome {position}",
        "material_scope": f"Approved scope {position}",
        "evidence_refs": [f"EV-{position:02d}"],
        "prior_learning": "Confirmed prior learning",
        "content_boundary": "Only the approved knowledge boundary",
        "must_not_preteach": ["Later topic"],
        "teaching_focus": "One assessable focus",
        "learning_difficulty": "One learner difficulty",
        "division_reason": "One capacity and progression reason",
        "following_connection": "The next approved topic",
    }


def division_content(*units: dict[str, object]) -> dict[str, object]:
    return {
        "division_key": "DIVISION-001",
        "scope_summary": "Approved textbook pages and course target",
        "lesson_count": len(units),
        "lesson_units": list(units),
        "coverage_check": {
            "all_evidence_covered": True,
            "overlap_free": True,
            "progression_rationale": "A reviewable learning progression",
            "unresolved_questions": [],
        },
    }


def validation_context(content: dict[str, object]) -> QualityValidationContext:
    evidence = [
        {"evidence_key": "EV-01", "supported_claim": "First approved claim"},
        {"evidence_key": "EV-02", "supported_claim": "Second approved claim"},
    ]
    return QualityValidationContext(
        organization_id=UUID("10000000-0000-4000-8000-000000000001"),
        project_id=UUID("10000000-0000-4000-8000-000000000002"),
        lesson_unit_id=None,
        content_release_id=UUID("10000000-0000-4000-8000-000000000003"),
        workflow_definition_version_id=UUID("10000000-0000-4000-8000-000000000004"),
        node_run_id=UUID("10000000-0000-4000-8000-000000000005"),
        source_type="artifact",
        source_id=UUID("10000000-0000-4000-8000-000000000006"),
        source_version_id=VERSION_ID,
        source_content_hash="a" * 64,
        source_content=content,
        validator_refs=(LESSON_DIVISION_SCHEMA_REF, LESSON_DIVISION_COVERAGE_REF),
        validator_set_hash="b" * 64,
        supporting_inputs={
            "content:material_evidence": {
                "material_evidence": evidence,
                "knowledge_boundary": {
                    "must_teach": ["First approved claim", "Second approved claim"],
                    "must_not_preteach": ["Later topic"],
                },
            }
        },
    )


def finding_codes(outcome: object) -> set[str]:
    findings = getattr(outcome, "findings")
    return {str(item["code"]) for item in findings}


def test_valid_division_maps_lesson_unit_key_to_domain_lesson_key() -> None:
    content = division_content(lesson_unit("LESSON-01", 1), lesson_unit("LESSON-02", 2))

    approved = build_approved_lesson_division(VERSION_ID, content)

    assert approved.version_id == VERSION_ID
    assert [(item.lesson_key, item.position) for item in approved.lessons] == [
        ("LESSON-01", 1),
        ("LESSON-02", 2),
    ]
    assert approved.lessons[0].scope_summary == "Approved scope 1"
    assert approved.lessons[0].objective_summary == "Observable outcome 1"
    assert approved.lessons[0].estimated_minutes == 40


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    (
        (lambda value: value.update(lesson_count=3), "LESSON_COUNT_MISMATCH"),
        (
            lambda value: value["lesson_units"][1].update(lesson_unit_key="LESSON-01"),
            "LESSON_UNIT_KEY_DUPLICATE",
        ),
        (
            lambda value: value["lesson_units"][1].update(position=3),
            "LESSON_POSITION_NON_CONTIGUOUS",
        ),
        (
            lambda value: value["lesson_units"][0].update(core_learning_outcome=" "),
            "LESSON_CORE_OUTCOME_EMPTY",
        ),
        (
            lambda value: value["lesson_units"][0].update(duration_minutes=90),
            "LESSON_CAPACITY_INVALID",
        ),
    ),
)
def test_schema_validator_rejects_count_key_order_objective_and_capacity_errors(
    mutate,
    expected_code: str,
) -> None:
    content = division_content(lesson_unit("LESSON-01", 1), lesson_unit("LESSON-02", 2))
    mutate(content)

    outcome = LessonDivisionSchemaValidator().validate(validation_context(content))

    assert outcome.passed is False
    assert expected_code in finding_codes(outcome)
    assert outcome.validator == LESSON_DIVISION_SCHEMA_REF


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    (
        (
            lambda value: value["lesson_units"][1].update(evidence_refs=[]),
            "MATERIAL_EVIDENCE_OMITTED",
        ),
        (
            lambda value: value["lesson_units"][1].update(evidence_refs=["EV-01"]),
            "MATERIAL_EVIDENCE_DUPLICATED",
        ),
        (
            lambda value: value["lesson_units"][1].update(evidence_refs=["EV-99"]),
            "MATERIAL_EVIDENCE_OUT_OF_SCOPE",
        ),
        (
            lambda value: value["coverage_check"].update(overlap_free=False),
            "LESSON_SCOPE_OVERLAP",
        ),
    ),
)
def test_coverage_validator_rejects_omitted_duplicate_out_of_scope_and_overlap(
    mutate,
    expected_code: str,
) -> None:
    content = division_content(lesson_unit("LESSON-01", 1), lesson_unit("LESSON-02", 2))
    mutate(content)

    outcome = LessonDivisionCoverageValidator().validate(validation_context(content))

    assert outcome.passed is False
    assert expected_code in finding_codes(outcome)
    assert outcome.validator == LESSON_DIVISION_COVERAGE_REF


def test_stable_key_diff_ignores_reorder_but_selects_changed_and_archived_keys() -> None:
    previous = division_content(
        lesson_unit("LESSON-01", 1),
        lesson_unit("LESSON-02", 2),
        lesson_unit("LESSON-03", 3),
    )
    current = division_content(
        deepcopy(lesson_unit("LESSON-02", 1)),
        deepcopy(lesson_unit("LESSON-01", 2)),
        lesson_unit("LESSON-04", 3),
    )
    current["lesson_units"][1]["core_learning_outcome"] = "A materially changed outcome"

    diff = diff_lesson_divisions(previous, current)

    assert diff.added_keys == ("LESSON-04",)
    assert diff.changed_keys == ("LESSON-01",)
    assert diff.unchanged_keys == ("LESSON-02",)
    assert diff.archived_keys == ("LESSON-03",)
    assert diff.stale_keys == ("LESSON-01", "LESSON-03")
