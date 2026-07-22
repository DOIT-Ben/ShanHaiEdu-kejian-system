from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scripts.build_builtin_generation_package import build_package
from scripts.golden_courseware_branch_inputs import (
    GOLDEN_PLANNING_NODE_KEYS,
    PROVIDER_MEDIA_NODE_KEYS,
    build_golden_branch_source_outputs,
    build_golden_branch_start_inputs,
)
from scripts.golden_courseware_content_validation import validate_content_fields
from scripts.golden_courseware_stage_inputs import (
    GOLDEN_CHAIN_INPUT_NODE_KEYS,
    MEDIA_BOUNDARY_OUTPUT_ONLY_NODE_KEYS,
    build_golden_chain_inputs,
)
from scripts.validate_golden_courseware import (
    GoldenCoursewareValidationError,
    _validate_intro,
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


def fail_golden_validation(code: str, message: str) -> None:
    raise GoldenCoursewareValidationError(code, message)


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
    assert len(model_nodes) == 22
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


def test_lesson_plan_has_twelve_sections_and_intro_is_a_separate_artifact() -> None:
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
        tendency: sum(option["primary_tendency"] == tendency for option in options)
        for tendency in (
            "science",
            "application",
            "story",
        )
    } == {"science": 3, "application": 3, "story": 3}
    scores = [option["recommendation_score"] for option in options]
    assert scores.count(max(scores)) == 1
    assert case["intro_selection"]["selection_method"] == "teacher_selected"
    assert case["intro_option_set"]["existing_idea_version_ref"] is None
    assert case["intro_selection"]["approval_ref"]["status"] == "approved"
    assert case["intro_selection"]["approval_ref"]["artifact_version_id"] == (
        case["intro_option_set"]["artifact_version_id"]
    )


def test_teacher_selection_may_override_the_unique_recommendation() -> None:
    case = copy.deepcopy(load_json(GOLDEN_CASE))
    non_top = min(
        case["intro_option_set"]["options"],
        key=lambda option: option["recommendation_score"],
    )
    case["intro_selection"].update(
        {
            "selection_method": "teacher_selected",
            "option_key": non_top["option_key"],
            "snapshot": copy.deepcopy(non_top),
        }
    )

    _validate_intro(case)

    case["intro_selection"]["selection_method"] = "policy_default"
    with pytest.raises(GoldenCoursewareValidationError) as caught:
        _validate_intro(case)
    assert caught.value.code == "GOLDEN_INTRO_SELECTION_INVALID"


def test_lesson_ppt_and_video_can_start_from_fixed_branch_inputs() -> None:
    case = load_json(GOLDEN_CASE)
    source = load_json(SOURCE)
    nodes = {node["template_key"]: node for node in source["nodes"]}
    package = validate_content_package(PACKAGE, contracts_root=CONTRACTS)
    source_outputs = build_golden_branch_source_outputs(case)
    branch_inputs = build_golden_branch_start_inputs(case)

    assert set(branch_inputs) == {
        "lesson_plan.generate",
        "ppt.content_analyze",
        "video.master_script.generate",
    }
    for node_key, payload in branch_inputs.items():
        generation = package.items[node_key]["spec"]
        input_key = generation["input_definition_ref"]["item_key"]
        fields = package.items[input_key]["spec"]["fields"]
        required_keys = {field["field_key"] for field in fields if field["required"]}
        assert required_keys <= payload.keys()
        assert payload.keys() <= {field["field_key"] for field in fields}

    lesson_input = branch_inputs["lesson_plan.generate"]
    lesson_output = source_outputs["lesson_plan.generate"]["teaching_content"]
    approved_lesson = lesson_input["lesson_unit_ref"]
    assert lesson_output["source_lesson_unit_key"] == approved_lesson["lesson_unit_key"]
    assert lesson_output["duration_minutes"] == approved_lesson["duration_minutes"]
    assert lesson_output["teaching_scope"] == approved_lesson["material_scope"]
    assert lesson_output["teaching_evidence_refs"] == approved_lesson["evidence_refs"]
    assert lesson_output["content_boundary"] == approved_lesson["content_boundary"]
    assert lesson_output["must_not_preteach"] == approved_lesson["must_not_preteach"]
    assert (
        lesson_input["lesson_unit_ref"]
        == source_outputs["lesson.division.generate"]["lesson_units"][0]
    )
    assert "prior_learning" in lesson_input["lesson_unit_ref"]
    assert "following_connection" in lesson_input["lesson_unit_ref"]
    assert lesson_input["material_evidence_ref"]["material_evidence"] == case["material_evidence"]

    ppt_input = branch_inputs["ppt.content_analyze"]
    assert ppt_input["approved_lesson_plan"] == source_outputs["lesson_plan.generate"]
    assert "confirmed_learner_facts" in ppt_input["approved_lesson_plan"]["learner_analysis"]
    assert "confirmed_facts" not in ppt_input["approved_lesson_plan"]["learner_analysis"]
    assert (
        ppt_input["approved_material_evidence"]["knowledge_boundary"] == case["knowledge_boundary"]
    )

    video_input = branch_inputs["video.master_script.generate"]
    assert video_input["selected_intro_snapshot_ref"] == case["intro_selection"]["snapshot"]
    assert "creative_concept" in video_input["selected_intro_snapshot_ref"]
    serialized_video_input = json.dumps(video_input, ensure_ascii=False)
    assert "lesson_plan" not in serialized_video_input
    assert "material_evidence" not in serialized_video_input
    assert "ppt" not in serialized_video_input
    assert video_input["video_duration_mode"] == "system_recommended"
    assert "video_target_duration_seconds" not in video_input
    assert case["ppt"]["analysis"]["recommended_page_count"] == 10
    assert case["video"]["master_script"]["target_duration_seconds"] == 90

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


def test_golden_outputs_cover_exact_planning_scope_without_fake_media() -> None:
    case = load_json(GOLDEN_CASE)
    package = validate_content_package(PACKAGE, contracts_root=CONTRACTS)
    outputs = build_golden_branch_source_outputs(case)
    entrypoints = set(package.manifest["entrypoints"])

    assert set(outputs) == set(GOLDEN_PLANNING_NODE_KEYS)
    assert set(GOLDEN_PLANNING_NODE_KEYS).isdisjoint(PROVIDER_MEDIA_NODE_KEYS)
    assert set(GOLDEN_PLANNING_NODE_KEYS) | set(PROVIDER_MEDIA_NODE_KEYS) == entrypoints
    for node_key, payload in outputs.items():
        generation = package.items[node_key]["spec"]
        output_key = generation["output_definition_ref"]["item_key"]
        expected_fields = {
            field["field_key"] for field in package.items[output_key]["spec"]["fields"]
        }
        assert set(payload) == expected_fields


def test_golden_planning_chain_reuses_exact_upstream_outputs() -> None:
    case = load_json(GOLDEN_CASE)
    outputs = build_golden_branch_source_outputs(case)
    chain_inputs = build_golden_chain_inputs(case)

    assert tuple(chain_inputs) == GOLDEN_CHAIN_INPUT_NODE_KEYS
    assert set(chain_inputs).isdisjoint(MEDIA_BOUNDARY_OUTPUT_ONLY_NODE_KEYS)
    assert "intro.generate_options" in outputs
    assert (
        chain_inputs["intro.generate_options"]["target_lesson_unit"]["lesson_unit_key"]
        == (case["intro_option_set"]["lesson_unit_key"])
    )
    assert (
        chain_inputs["intro.generate_options"]["target_material_evidence"]["knowledge_boundary"]
        == (case["knowledge_boundary"])
    )
    assert (
        chain_inputs["ppt.outline.generate"]["ppt_analysis_ref"] == outputs["ppt.content_analyze"]
    )
    assert (
        chain_inputs["ppt.pages.generate"]["approved_outline_ref"]
        == outputs["ppt.outline.generate"]
    )
    assert chain_inputs["ppt.cover.prompt.generate"]["cover_page_context"] == next(
        page for page in outputs["ppt.pages.generate"]["page_specs"] if page["page_type"] == "cover"
    )
    assert (
        chain_inputs["ppt.body_asset_prompts.generate"]["body_page_specs"]
        == outputs["ppt.pages.generate"]
    )
    assert (
        chain_inputs["video.rough_storyboard.generate"]["rough_master_script_ref"]
        == outputs["video.master_script.generate"]
    )
    assert (
        chain_inputs["video.style_master.prompt.generate"]["style_rough_storyboard_ref"]
        == outputs["video.rough_storyboard.generate"]
    )
    assert (
        chain_inputs["video.asset_inventory.generate"]["inventory_rough_storyboard_ref"]
        == outputs["video.rough_storyboard.generate"]
    )
    assert (
        chain_inputs["video.asset_prompts.generate"]["current_video_asset_inventory"]
        == outputs["video.asset_inventory.generate"]
    )


def test_course_grounded_intro_options_keep_one_current_contract() -> None:
    case = load_json(GOLDEN_CASE)
    source = load_json(SOURCE)
    option_set = case["intro_option_set"]
    options = option_set["options"]
    generate_options = next(
        node for node in source["nodes"] if node["template_key"] == "intro.generate_options"
    )
    target_lesson = next(
        unit
        for unit in case["lesson_division"]["lesson_units"]
        if unit["lesson_unit_key"] == option_set["lesson_unit_key"]
    )

    assert option_set["knowledge_point"] == target_lesson["teaching_focus"]
    assert Counter(option["primary_tendency"] for option in options) == Counter(
        {"science": 3, "application": 3, "story": 3}
    )
    assert any(len(option["secondary_tendencies"]) >= 2 for option in options)
    assert all(option["creative_concept"] for option in options)
    assert all(option["lesson_unit_key"] == target_lesson["lesson_unit_key"] for option in options)
    assert all(option["knowledge_point"] == target_lesson["teaching_focus"] for option in options)
    assert all(option["course_anchor"] for option in options)
    assert all(option["must_not_preteach"] for option in options)
    scores = [option["recommendation_score"] for option in options]
    assert scores.count(max(scores)) == 1
    input_fields = {field["field_key"]: field for field in generate_options["input"]["fields"]}
    assert "general_teacher_preferences" not in input_fields
    assert {
        key
        for key, field in input_fields.items()
        if field["source"] == "teacher" and key.endswith("preferences")
    } == {"medium_preferences", "creative_preferences"}
    assert input_fields["duration_preference_seconds"]["source"] == "teacher"
    assert generate_options["input"]["conditional_requirements"] == [
        {
            "when": {"field_key": "generation_mode", "equals": "default_nine"},
            "forbidden_fields": ["existing_idea_ref"],
        },
        {
            "when": {"field_key": "generation_mode", "equals": "refine_existing"},
            "required_fields": ["existing_idea_ref"],
        },
    ]

    output_fields = {field["field_key"] for field in generate_options["output"]["fields"]}
    assert {"generation_mode", "existing_idea_version_ref"} <= output_fields


def test_retired_intro_contract_tokens_are_absent_from_current_tree() -> None:
    retired_tokens = (
        "intro." + "ideate",
        "intro." + "anchor",
        "intro_" + "independent_ideas",
        "independent_" + "without_course",
        "双" + "快照",
        "锚点" + "节点",
        "锚点" + "隔离",
        "独立" + "概念",
        "即使没有课程" + "回接",
    )
    active_roots = (ROOT / "workflow", CONTRACTS, ROOT / "docs", ROOT / "scripts")
    text_suffixes = {".json", ".md", ".py", ".yaml", ".yml", ".ts"}
    offenders: dict[str, list[str]] = {}
    for active_root in active_roots:
        for path in active_root.rglob("*"):
            if not path.is_file() or path.suffix not in text_suffixes:
                continue
            text = path.read_text(encoding="utf-8")
            matches = [token for token in retired_tokens if token in text]
            if matches:
                offenders[path.relative_to(ROOT).as_posix()] = matches

    assert offenders == {}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda case: case["ppt"]["analysis"].pop("interaction_points"),
        lambda case: case["video"]["asset_inventory"]["assets"][0].pop("identity_key"),
        lambda case: case["video"]["audio_plan"]["tracks"][0].pop("volume_intent"),
    ],
)
def test_golden_planning_output_sources_cannot_silently_drift(mutate: Any) -> None:
    case = copy.deepcopy(load_json(GOLDEN_CASE))
    mutate(case)

    with pytest.raises(GoldenCoursewareValidationError) as caught:
        validate_golden_case(case, package_root=PACKAGE, contracts_root=CONTRACTS)
    assert caught.value.code == "GOLDEN_CONTENT_SOURCE_INCOMPLETE"


def test_new_required_content_field_invalidates_stale_golden_output() -> None:
    case = load_json(GOLDEN_CASE)
    package = validate_content_package(PACKAGE, contracts_root=CONTRACTS)
    output = build_golden_branch_source_outputs(case)["ppt.content_analyze"]
    fields = copy.deepcopy(package.items["ppt.content_analyze.output"]["spec"]["fields"])
    fields.append(
        {
            "field_key": "new_required_contract_field",
            "type": "text",
            "required": True,
        }
    )

    with pytest.raises(GoldenCoursewareValidationError) as caught:
        validate_content_fields(
            output,
            fields,
            path="ppt.content_analyze",
            fail=fail_golden_validation,
        )
    assert caught.value.code == "GOLDEN_CONTENT_SHAPE_INVALID"


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
                {"duration_seconds": 31}
            ),
            "GOLDEN_VIDEO_SHOT_DURATION_INVALID",
        ),
        (
            lambda case: case["video"]["audio_plan"].update({"tracks": []}),
            "GOLDEN_AUDIO_TRACKS_MISSING",
        ),
        (
            lambda case: case.update({"delivery_expectations": {}}),
            "GOLDEN_DELIVERY_EXPECTATION_INVALID",
        ),
        (
            lambda case: case["intro_option_set"]["options"][0].update({"must_not_preteach": []}),
            "GOLDEN_INTRO_KNOWLEDGE_BOUNDARY_INVALID",
        ),
        (
            lambda case: case["intro_option_set"].update(
                {"lesson_unit_key": "LESSON-DOES-NOT-EXIST"}
            ),
            "GOLDEN_INTRO_LESSON_SOURCE_INVALID",
        ),
        (
            lambda case: case["ppt"]["page_specs"][0].update({"source_refs": ["MISSING-REF"]}),
            "GOLDEN_PPT_SOURCE_REF_INVALID",
        ),
        (
            lambda case: case["video"]["asset_inventory"]["assets"].append(
                copy.deepcopy(case["video"]["asset_inventory"]["assets"][0])
            ),
            "GOLDEN_VIDEO_ASSET_KEY_DUPLICATE",
        ),
        (
            lambda case: case["source"]["verification"].update({"hash_verified": False}),
            "GOLDEN_SOURCE_VERIFICATION_INCOMPLETE",
        ),
        (
            lambda case: case["lesson_plan"]["sections"]["teaching_process"][0].pop(
                "board_updates"
            ),
            "GOLDEN_CONTENT_SOURCE_INVALID",
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
