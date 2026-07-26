from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from apps.api.artifact_quality.contracts import QualityValidationContext
from apps.api.content_runtime.definition_projection import build_content_json_schema
from apps.api.lessons.lesson_plan_quality import (
    LEGACY_LESSON_PLAN_SCOPE_REF,
    LEGACY_LESSON_PLAN_TEACHING_QUALITY_REF,
    LESSON_PLAN_SCOPE_REF,
    LESSON_PLAN_TEACHING_QUALITY_REF,
    LessonPlanScopeQualityValidator,
    LessonPlanTeachingQualityValidator,
)
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"
OUTPUT_DEFINITION = (
    ROOT
    / "contracts/fixtures/primary-math-courseware-package/items/lesson-plan-generate-output.json"
)


def test_lesson_plan_quality_accepts_real_parser_pages_only_evidence() -> None:
    context = _context_with_pages_only_evidence()

    assert LessonPlanScopeQualityValidator().validate(context).passed is True
    assert LessonPlanTeachingQualityValidator().validate(context).passed is True
    legacy_scope = LessonPlanScopeQualityValidator(
        ref=LEGACY_LESSON_PLAN_SCOPE_REF,
        include_page_evidence=False,
    ).validate(context)
    legacy_teaching = LessonPlanTeachingQualityValidator(
        ref=LEGACY_LESSON_PLAN_TEACHING_QUALITY_REF,
        include_page_evidence=False,
    ).validate(context)
    assert legacy_scope.validator == LEGACY_LESSON_PLAN_SCOPE_REF
    assert legacy_teaching.validator == LEGACY_LESSON_PLAN_TEACHING_QUALITY_REF
    assert legacy_scope.passed is False
    assert legacy_teaching.passed is False


def _context_with_pages_only_evidence() -> QualityValidationContext:
    case = cast(
        dict[str, Any],
        json.loads(GOLDEN_CASE.read_text(encoding="utf-8")),
    )
    outputs = build_golden_branch_source_outputs(case)
    content = cast(dict[str, Any], outputs["lesson_plan.generate"])
    teaching_content = cast(dict[str, Any], content["teaching_content"])
    lesson_key = cast(str, teaching_content["source_lesson_unit_key"])
    division = cast(dict[str, Any], outputs["lesson.division.generate"])
    lesson_units = cast(list[dict[str, Any]], division["lesson_units"])
    lesson = next(item for item in lesson_units if item["lesson_unit_key"] == lesson_key)
    evidence = cast(list[dict[str, Any]], case["material_evidence"])
    definition = cast(
        dict[str, Any],
        json.loads(OUTPUT_DEFINITION.read_text(encoding="utf-8")),
    )
    spec = cast(dict[str, Any], definition["spec"])
    return QualityValidationContext(
        organization_id=UUID("01930000-0000-7000-8000-000000000100"),
        project_id=UUID("01930000-0000-7000-8000-000000000101"),
        lesson_unit_id=UUID("01930000-0000-7000-8000-000000000102"),
        content_release_id=UUID("01930000-0000-7000-8000-000000000103"),
        workflow_definition_version_id=UUID("01930000-0000-7000-8000-000000000104"),
        node_run_id=UUID("01930000-0000-7000-8000-000000000105"),
        source_type="artifact",
        source_id=UUID("01930000-0000-7000-8000-000000000106"),
        source_version_id=UUID("01930000-0000-7000-8000-000000000107"),
        source_content_hash="a" * 64,
        source_content=content,
        validator_refs=(LESSON_PLAN_SCOPE_REF, LESSON_PLAN_TEACHING_QUALITY_REF),
        validator_set_hash="b" * 64,
        source_schema=build_content_json_schema(spec),
        lesson_key=lesson_key,
        supporting_inputs={
            "approval:lesson_division": {
                "division_key": division["division_key"],
                "lesson_unit": deepcopy(lesson),
            },
            "content:material_evidence": {
                "pages": [
                    {
                        "page_number": 1,
                        "text_blocks": [
                            {
                                "block_id": item["evidence_key"],
                                "text": item["supported_claim"],
                            }
                            for item in evidence
                        ],
                        "image_references": [],
                    }
                ]
            },
        },
        supporting_input_versions={
            "approval:lesson_division": UUID("01930000-0000-7000-8000-000000000110"),
            "content:material_evidence": UUID("01930000-0000-7000-8000-000000000111"),
        },
    )
