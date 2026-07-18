from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scripts.build_builtin_generation_package import build_package
from scripts.validate_golden_courseware import (
    GoldenCoursewareValidationError,
    validate_golden_case,
)
from workflow.content_package import DEFAULT_CONTEXT_SOURCES, validate_content_package

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
SOURCE = ROOT / "workflow/builtin/primary_math_courseware/generation-source.json"
PACKAGE = CONTRACTS / "fixtures/primary-math-courseware-package"
CATALOG = CONTRACTS / "fixtures/workflow-node-generation-bindings/primary-math-courseware.json"
GOLDEN_CASE = CONTRACTS / "fixtures/golden-projects/numbers-1-to-5/golden-project.json"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_builtin_package_is_reproducible_and_valid(tmp_path: Path) -> None:
    generated = tmp_path / "package"
    build_package(SOURCE, generated, contracts_root=CONTRACTS)

    generated_files = sorted(path.relative_to(generated) for path in generated.rglob("*.json"))
    tracked_files = sorted(path.relative_to(PACKAGE) for path in PACKAGE.rglob("*.json"))
    assert generated_files == tracked_files
    for relative in generated_files:
        assert (generated / relative).read_bytes() == (PACKAGE / relative).read_bytes()

    package = validate_content_package(PACKAGE, contracts_root=CONTRACTS)
    assert package.manifest["package_key"] == "shanhai.primary_math.courseware"


def test_every_model_node_resolves_a_generation_template() -> None:
    catalog = load_json(CATALOG)
    package = validate_content_package(PACKAGE, contracts_root=CONTRACTS)
    available = {
        key for key, item in package.items.items() if item["kind"] == "generation_template"
    }

    model_nodes = [
        node for node in catalog["nodes"] if node["execution_kind"] == "model_generation"
    ]
    assert len(model_nodes) == 23
    assert {node["generation_template_ref"]["item_key"] for node in model_nodes} <= available


def test_generation_source_matches_catalog_capabilities_and_contexts() -> None:
    catalog = load_json(CATALOG)
    source = load_json(SOURCE)
    model_nodes = {
        node["node_key"]: node
        for node in catalog["nodes"]
        if node["execution_kind"] == "model_generation"
    }
    source_nodes = {node["template_key"]: node for node in source["nodes"]}

    assert source_nodes.keys() == model_nodes.keys()
    for key, node in source_nodes.items():
        catalog_node = model_nodes[key]
        assert node["model_capability"] == catalog_node["model_capability"]
        assert [
            binding["source"] for binding in node["prompt"]["context_bindings"]
        ] == catalog_node["context_policy"]["allowed_sources"]

    catalog_context_sources = {
        context
        for node in model_nodes.values()
        for context in node["context_policy"]["allowed_sources"]
    }
    assert catalog_context_sources <= DEFAULT_CONTEXT_SOURCES


def test_lesson_division_prompt_preserves_reference_method_and_scope() -> None:
    source = load_json(SOURCE)
    division = next(
        node for node in source["nodes"] if node["template_key"] == "lesson.division.generate"
    )
    prompt = "\n".join(
        division["prompt"][key] for key in ("role", "task", "method", "quality_gate")
    )

    assert "40分钟" in prompt
    assert "只生成课时划分" in prompt
    assert "认知难度而非机械页码" in prompt
    assert "一个核心学习结果" in prompt
    assert "不重叠、不遗漏" in prompt
    assert "不要同时生成详细教案" in prompt


def test_lesson_plan_content_definition_has_exact_twelve_sections() -> None:
    package = validate_content_package(PACKAGE, contracts_root=CONTRACTS)
    lesson_plan_output = package.items["lesson_plan.generate.output"]["spec"]
    assert [field["field_key"] for field in lesson_plan_output["fields"]] == [
        "teaching_content",
        "material_analysis",
        "learner_analysis",
        "design_intent",
        "teaching_objectives",
        "key_difficulties_and_strategies",
        "preparation",
        "teaching_process",
        "board_design",
        "lesson_summary",
        "differentiated_homework",
        "teaching_reflection",
    ]


def test_golden_case_matches_schema_and_business_invariants() -> None:
    case = load_json(GOLDEN_CASE)
    schema = load_json(CONTRACTS / "golden-courseware-case.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(case)
    validate_golden_case(case, package_root=PACKAGE, contracts_root=CONTRACTS)

    assert case["source"]["sha256"] == (
        "22af2828fba7d3524fca1a77707d18977624bac790870dd219b459d5b830b9e1"
    )
    assert case["source"]["pdf_page_indexes"] == [3, 4, 5]
    assert case["source"]["printed_pages"] == [14, 15, 16]
    assert case["lesson_division"]["lesson_count"] == 1
    assert case["lesson_division"]["lesson_units"][0]["duration_minutes"] == 40

    forbidden = set(case["knowledge_boundary"]["must_not_preteach"])
    assert {"比较大小", "第几", "分与合", "加法", "减法", "0的认识"} <= forbidden


def test_lesson_plan_has_twelve_sections_and_intro_is_independent() -> None:
    case = load_json(GOLDEN_CASE)
    assert list(case["lesson_plan"]["sections"]) == [
        "teaching_content",
        "material_analysis",
        "learner_analysis",
        "design_intent",
        "teaching_objectives",
        "key_difficulties_and_strategies",
        "preparation",
        "teaching_process",
        "board_design",
        "lesson_summary",
        "differentiated_homework",
        "teaching_reflection",
    ]
    assert "intro_option_set" not in case["lesson_plan"]["sections"]

    options = case["intro_option_set"]["options"]
    assert len(options) == 9
    assert {
        category: sum(option["category"] == category for option in options)
        for category in (
            "science",
            "application",
            "story",
        )
    } == {"science": 3, "application": 3, "story": 3}
    scores = [option["recommendation_score"] for option in options]
    assert scores.count(max(scores)) == 1


def test_ppt_and_video_can_start_from_fixed_independent_inputs() -> None:
    case = load_json(GOLDEN_CASE)
    source = load_json(SOURCE)
    nodes = {node["template_key"]: node for node in source["nodes"]}

    assert case["ppt"]["source_lesson_plan_key"] == case["lesson_plan"]["lesson_plan_key"]
    assert case["video"]["selected_intro_option_key"] == case["intro_selection"]["option_key"]

    video_sources = {
        binding["source"]
        for key, node in nodes.items()
        if key.startswith("video.") or key.startswith("audio.")
        for binding in node["prompt"]["context_bindings"]
    }
    assert "intro_selection.snapshot" in video_sources
    assert "lesson_plan.approved_version" not in video_sources
    assert "material.approved_parse" not in video_sources
    assert "ppt_outline.approved_version" not in video_sources

    ppt_sources = {
        binding["source"]
        for key, node in nodes.items()
        if key.startswith("ppt.")
        for binding in node["prompt"]["context_bindings"]
    }
    assert "lesson_plan.approved_version" in ppt_sources


def test_golden_fixture_does_not_commit_source_or_local_paths() -> None:
    case = load_json(GOLDEN_CASE)
    serialized = json.dumps(case, ensure_ascii=False)
    assert case["source"]["verification"]["raw_source_committed"] is False
    assert "E:\\" not in serialized
    assert "D:\\" not in serialized
    assert "C:\\Users" not in serialized


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda case: case["video"]["source_policy"]["allowed_sources"].append(
                "lesson_plan.approved_version"
            ),
            "GOLDEN_VIDEO_CONTEXT_INVALID",
        ),
        (
            lambda case: case["ppt"]["page_specs"][1]["canvas"].update(
                {"background_color": "#F8FAFC"}
            ),
            "GOLDEN_PPT_BODY_BACKGROUND_INVALID",
        ),
        (
            lambda case: case["video"]["fine_storyboard"]["shots"][0].update(
                {"duration_seconds": 12}
            ),
            "GOLDEN_VIDEO_SHOT_DURATION_INVALID",
        ),
    ],
)
def test_golden_business_invariants_reject_contract_drift(
    mutate: Any,
    code: str,
) -> None:
    case = copy.deepcopy(load_json(GOLDEN_CASE))
    mutate(case)

    with pytest.raises(GoldenCoursewareValidationError) as caught:
        validate_golden_case(case, package_root=PACKAGE, contracts_root=CONTRACTS)
    assert caught.value.code == code
