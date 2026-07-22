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


def _content(mode: str) -> dict[str, Any]:
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    content = build_golden_branch_source_outputs(case)["intro.generate_options"]
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
