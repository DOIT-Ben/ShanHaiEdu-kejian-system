from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest

from apps.api.artifact_quality.contracts import QualityValidationContext
from apps.api.content_runtime.definition_projection import build_content_json_schema
from apps.api.intro_options.quality import (
    INTRO_OPTION_SCHEMA_REF,
    INTRO_SINGLE_ANCHOR_REF,
    INTRO_UNIQUE_RECOMMENDATION_REF,
    IntroOptionSchemaQualityValidator,
    IntroSingleAnchorQualityValidator,
    IntroUniqueRecommendationQualityValidator,
)
from apps.api.intro_options.quality_legacy import (
    LEGACY_INTRO_OPTION_SCHEMA_REF,
    LEGACY_INTRO_SINGLE_ANCHOR_REF,
    PREVIOUS_INTRO_SINGLE_ANCHOR_REF,
)
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"
OUTPUT_DEFINITION = (
    ROOT
    / "contracts/fixtures/primary-math-courseware-package/items/intro-generate-options-output.json"
)
SOURCE_VERSION_ID = UUID("01930000-0000-7000-8000-000000000109")


@pytest.mark.parametrize("mode", ["default_nine", "refine_existing"])
def test_one_and_nine_modes_pass_the_same_declared_quality_chain(mode: str) -> None:
    context = _context(_content(mode))

    outcomes = (
        IntroOptionSchemaQualityValidator().validate(context),
        IntroSingleAnchorQualityValidator().validate(context),
        IntroUniqueRecommendationQualityValidator().validate(context),
    )

    assert tuple(item.validator for item in outcomes) == (
        INTRO_OPTION_SCHEMA_REF,
        INTRO_SINGLE_ANCHOR_REF,
        INTRO_UNIQUE_RECOMMENDATION_REF,
    )
    assert all(item.passed for item in outcomes), outcomes


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value["options"].pop(), "INTRO_OPTION_COUNT_INVALID"),
        (
            lambda value: value["options"][0].update(primary_tendency="application"),
            "INTRO_TENDENCY_DISTRIBUTION_INVALID",
        ),
        (
            lambda value: value.update(source_material_evidence_keys=[]),
            "INTRO_MATERIAL_EVIDENCE_INVALID",
        ),
    ],
)
def test_default_nine_rejects_cardinality_distribution_and_evidence_drift(
    mutate,
    code: str,
) -> None:
    content = _content("default_nine")
    mutate(content)

    outcome = IntroOptionSchemaQualityValidator().validate(_context(content))

    assert outcome.passed is False
    assert code in {str(item["code"]) for item in outcome.findings}


def test_refine_existing_requires_one_exact_source_and_one_option() -> None:
    content = _content("refine_existing")
    content["source_intro_option_version_refs"] = []

    outcome = IntroOptionSchemaQualityValidator().validate(_context(content))

    assert outcome.passed is False
    assert "INTRO_SOURCE_CARDINALITY_INVALID" in {str(item["code"]) for item in outcome.findings}


def test_real_parser_page_evidence_is_accepted() -> None:
    context = _context(_content("default_nine"))
    material = cast(dict[str, Any], context.supporting_inputs["content:material_evidence"])
    flat_evidence = cast(list[dict[str, Any]], material.pop("material_evidence"))
    material["pages"] = [
        {
            "image_references": [],
            "text_blocks": [
                {"block_id": item["evidence_key"], "text": item.get("summary", "evidence")}
                for item in flat_evidence
            ],
        }
    ]

    outcome = IntroSingleAnchorQualityValidator().validate(context)
    legacy = IntroSingleAnchorQualityValidator(
        ref=LEGACY_INTRO_SINGLE_ANCHOR_REF,
        include_page_evidence=False,
    ).validate(context)

    assert outcome.passed is True, outcome.findings
    assert legacy.validator == LEGACY_INTRO_SINGLE_ANCHOR_REF
    assert legacy.passed is False


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda options: options[1].update(option_key=options[0]["option_key"]),
            "INTRO_OPTION_KEY_INVALID",
        ),
        (
            lambda options: options[0].update(option_key="INTRO-APP-99"),
            "INTRO_OPTION_KEY_INVALID",
        ),
        (
            lambda options: options[1].update(
                creative_concept=f"  {options[0]['creative_concept']}  "
            ),
            "INTRO_OPTION_CONTENT_DUPLICATED",
        ),
    ],
)
def test_default_nine_rejects_duplicate_or_mismatched_option_identity(mutate, code: str) -> None:
    content = _content("default_nine")
    mutate(cast(list[dict[str, Any]], content["options"]))

    outcome = IntroOptionSchemaQualityValidator().validate(_context(content))

    assert outcome.passed is False
    assert code in {str(item["code"]) for item in outcome.findings}


def test_release_1_4_schema_keeps_its_pre_identity_validation_behavior() -> None:
    content = _content("default_nine")
    options = cast(list[dict[str, Any]], content["options"])
    options[1]["option_key"] = options[0]["option_key"]

    outcome = IntroOptionSchemaQualityValidator(
        ref=LEGACY_INTRO_OPTION_SCHEMA_REF,
        enforce_default_nine_identity=False,
    ).validate(_context(content))

    assert outcome.validator == LEGACY_INTRO_OPTION_SCHEMA_REF
    assert outcome.passed is True, outcome.findings


def test_unique_recommendation_and_no_preteach_fail_closed() -> None:
    content = _content("default_nine")
    options = cast(list[dict[str, Any]], content["options"])
    maximum = max(cast(int, option["recommendation_score"]) for option in options)
    non_maximum = next(option for option in options if option["recommendation_score"] != maximum)
    non_maximum["recommendation_score"] = maximum
    options[0]["creative_concept"] = "直接讲出比较大小的方法"

    schema = IntroOptionSchemaQualityValidator().validate(_context(content))
    recommendation = IntroUniqueRecommendationQualityValidator().validate(_context(content))

    assert schema.passed is False
    assert "INTRO_PRETEACH_VIOLATION" in {str(item["code"]) for item in schema.findings}
    assert recommendation.passed is False
    assert "INTRO_RECOMMENDATION_NOT_UNIQUE" in {
        str(item["code"]) for item in recommendation.findings
    }


def test_secondary_tendencies_are_not_required_but_child_safety_still_fails_closed() -> None:
    content = _content("default_nine")
    options = cast(list[dict[str, Any]], content["options"])
    for option in options:
        option.pop("secondary_tendencies", None)
    options[0]["hook"] = "安排儿童独自使用明火完成实验"

    outcome = IntroOptionSchemaQualityValidator().validate(_context(content))

    codes = {str(item["code"]) for item in outcome.findings}
    assert "INTRO_TENDENCY_DISTRIBUTION_INVALID" not in codes
    assert "INTRO_CHILD_SAFETY_INVALID" in codes


def test_course_anchor_rejects_wrong_frozen_teaching_focus() -> None:
    content = _content("default_nine")
    options = cast(list[dict[str, Any]], content["options"])
    content["source_knowledge_point"] = "比较大小"
    for option in options:
        option["knowledge_point"] = "比较大小"

    _assert_anchor_finding(content, "INTRO_COURSE_ANCHOR_INVALID")


def test_course_anchor_rejects_missing_frozen_preteach_boundary() -> None:
    content = _content("default_nine")
    options = cast(list[dict[str, Any]], content["options"])
    for option in options:
        option["must_not_preteach"] = ["无"]

    _assert_anchor_finding(content, "INTRO_PRETEACH_BOUNDARY_INVALID")


def test_course_anchor_rejects_frozen_later_topic_in_intro_content() -> None:
    content = _content("default_nine")
    options = cast(list[dict[str, Any]], content["options"])
    options[0]["creative_concept"] = "观察两组信号并比较大小"

    _assert_anchor_finding(content, "INTRO_PRETEACH_VIOLATION")


def test_course_anchor_allows_teacher_fit_reason_to_restate_frozen_boundary() -> None:
    content = _content("default_nine")
    options = cast(list[dict[str, Any]], content["options"])
    options[0]["fit_reason"] = "理货任务不涉及比较大小或序数，只在1～5范围内建立对应。"  # noqa: RUF001

    outcome = IntroSingleAnchorQualityValidator().validate(_context(content))
    previous = IntroSingleAnchorQualityValidator(
        ref=PREVIOUS_INTRO_SINGLE_ANCHOR_REF,
        scan_teacher_fit_reason=True,
    ).validate(_context(content))

    assert outcome.passed is True, outcome.findings
    assert previous.validator == PREVIOUS_INTRO_SINGLE_ANCHOR_REF
    assert previous.passed is False
    assert "INTRO_PRETEACH_VIOLATION" in {str(item["code"]) for item in previous.findings}


def _assert_anchor_finding(content: dict[str, Any], code: str) -> None:
    outcome = IntroSingleAnchorQualityValidator().validate(_context(content))

    assert outcome.passed is False
    assert code in {str(item["code"]) for item in outcome.findings}


def _content(mode: str) -> dict[str, Any]:
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    content = build_golden_branch_source_outputs(case)["intro.generate_options"]
    for option in cast(list[dict[str, Any]], content["options"]):
        option.pop("secondary_tendencies", None)
    if mode == "default_nine":
        return content
    content["generation_mode"] = "refine_existing"
    content["source_intro_option_version_refs"] = [str(SOURCE_VERSION_ID)]
    content["options"] = [deepcopy(content["options"][0])]
    content["recommendation_summary"] = {
        "recommended_option_key": content["options"][0]["option_key"],
        "single_highest_score": True,
    }
    return content


def _context(content: dict[str, Any]) -> QualityValidationContext:
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    division = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    lesson = next(
        item
        for item in division["lesson_units"]
        if item["lesson_unit_key"] == content["source_lesson_unit_key"]
    )
    definition = json.loads(OUTPUT_DEFINITION.read_text(encoding="utf-8"))
    supporting = {
        "approval:lesson_division": {
            "division_key": division["division_key"],
            "lesson_unit": deepcopy(lesson),
        },
        "content:material_evidence": {
            "material_evidence": deepcopy(case["material_evidence"]),
        },
    }
    versions = {
        "approval:lesson_division": UUID("01930000-0000-7000-8000-000000000110"),
        "content:material_evidence": UUID("01930000-0000-7000-8000-000000000111"),
    }
    if content["generation_mode"] == "refine_existing":
        supporting["artifact:intro_option_set_source"] = _content("default_nine")
        versions["artifact:intro_option_set_source"] = SOURCE_VERSION_ID
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
        validator_refs=(
            INTRO_OPTION_SCHEMA_REF,
            INTRO_SINGLE_ANCHOR_REF,
            INTRO_UNIQUE_RECOMMENDATION_REF,
        ),
        validator_set_hash="b" * 64,
        source_schema=build_content_json_schema(definition["spec"]),
        lesson_key=cast(str, content["source_lesson_unit_key"]),
        supporting_inputs=supporting,
        supporting_input_versions=versions,
    )
