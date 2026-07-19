from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from apps.api.model_gateway.contracts import ModelCapability
from workflow.node_generation_binding import (
    REGISTERED_MODEL_CAPABILITIES,
    NodeGenerationBindingError,
    validate_workflow_node_catalog,
)


def test_workflow_and_gateway_share_one_model_capability_registry() -> None:
    workflow_capabilities = {
        capability.value
        for capability in ModelCapability
        if capability not in {ModelCapability.TEXT_SMOKE}
    }

    assert REGISTERED_MODEL_CAPABILITIES == workflow_capabilities


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
SCHEMA_PATH = CONTRACTS / "workflow-node-generation-binding.schema.json"
FIXTURE_PATH = CONTRACTS / "fixtures/workflow-node-generation-bindings/primary-math-courseware.json"
CLI_PATH = ROOT / "scripts/validate_workflow_node_catalog.py"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def load_schema() -> dict[str, Any]:
    return load_object(SCHEMA_PATH)


def load_catalog() -> dict[str, Any]:
    return load_object(FIXTURE_PATH)


def node_by_key(catalog: dict[str, Any], node_key: str) -> dict[str, Any]:
    return next(node for node in catalog["nodes"] if node["node_key"] == node_key)


def assert_rejected(catalog: dict[str, Any], code: str) -> None:
    with pytest.raises(NodeGenerationBindingError) as caught:
        validate_workflow_node_catalog(catalog, schema=load_schema())
    assert caught.value.code == code


def test_schema_and_complete_primary_math_catalog_are_valid() -> None:
    schema = load_schema()
    catalog = load_catalog()

    Draft202012Validator.check_schema(schema)
    cast(Any, Draft202012Validator(schema)).validate(catalog)
    validated = validate_workflow_node_catalog(catalog, schema=schema)

    node_keys = {node["node_key"] for node in catalog["nodes"]}
    assert len(node_keys) >= 45
    assert {
        "material.parse",
        "lesson.division.generate",
        "lesson_plan.generate",
        "intro.generate_options",
        "ppt.pages.generate",
        "ppt.cover.image.generate",
        "ppt.body_assets.generate",
        "video.master_script.generate",
        "video.fine_storyboard.generate",
        "video.shots.generate",
        "audio.tts.generate",
        "video.timeline.assemble",
        "delivery.package",
    }.issubset(node_keys)
    assert validated.catalog == catalog
    assert len(validated.content_hash) == 64


def test_catalog_encodes_context_and_reference_asset_boundaries() -> None:
    catalog = load_catalog()

    division = node_by_key(catalog, "lesson.division.generate")
    assert division["context_policy"] == {
        "mode": "declared",
        "allowed_sources": ["material.approved_parse"],
        "forbidden_sources": [],
    }
    assert division["reference_asset_policy"] == {"mode": "none", "roles": []}

    generate_options = node_by_key(catalog, "intro.generate_options")
    assert generate_options["context_policy"]["mode"] == "declared"
    assert set(generate_options["context_policy"]["allowed_sources"]) == {
        "lesson_division.approved_version",
        "material.approved_parse",
    }
    assert {
        "lesson_plan.approved_version",
        "ppt_outline.approved_version",
    }.issubset(generate_options["context_policy"]["forbidden_sources"])

    video_script = node_by_key(catalog, "video.master_script.generate")
    assert video_script["context_policy"]["allowed_sources"] == ["intro_selection.snapshot"]
    assert {"lesson_plan.approved_version", "material.approved_parse"}.issubset(
        video_script["context_policy"]["forbidden_sources"]
    )

    reference_modes = {node["reference_asset_policy"]["mode"] for node in catalog["nodes"]}
    assert reference_modes == {"none", "optional", "required"}
    shot_generation = node_by_key(catalog, "video.shots.generate")
    assert shot_generation["reference_asset_policy"]["mode"] == "required"
    assert any(
        role["requirement"] == "required"
        for role in shot_generation["reference_asset_policy"]["roles"]
    )


def test_catalog_hides_internal_structure_and_exposes_only_business_prompt() -> None:
    catalog = load_catalog()

    lesson_plan = node_by_key(catalog, "lesson_plan.generate")
    assert lesson_plan["prompt_exposure_policy"] == {
        "teacher_business_prompt": "editable",
        "internal_template": "server_only",
        "output_contract": "server_only",
        "validation_and_repair": "server_only",
        "provider_format": "server_only",
        "structure_change_authority": "administrator_release_only",
    }
    internal_evaluation = node_by_key(catalog, "video.classroom_quality.evaluate")
    assert internal_evaluation["prompt_exposure_policy"]["teacher_business_prompt"] == ("hidden")
    deterministic = node_by_key(catalog, "video.timeline.assemble")
    assert deterministic["prompt_exposure_policy"]["teacher_business_prompt"] == ("not_applicable")


def test_catalog_hash_is_deterministic_for_semantically_identical_objects() -> None:
    first = load_catalog()
    second = json.loads(json.dumps(first, ensure_ascii=False, sort_keys=True))

    first_validated = validate_workflow_node_catalog(first, schema=load_schema())
    second_validated = validate_workflow_node_catalog(second, schema=load_schema())

    assert first_validated.canonical_json == second_validated.canonical_json
    assert first_validated.content_hash == second_validated.content_hash
    assert first_validated.content_hash == (
        "268f503e9e7e455aab936e885d1c67b1934384d45c2ef0e4d0399683e579e7ea"
    )


@pytest.mark.parametrize(
    ("execution_kind", "remove", "add"),
    [
        ("model_generation", "generation_template_ref", {}),
        ("deterministic", "executor_ref", {"model_capability": "text.structured.test"}),
        ("human_gate", "approval_policy", {"executor_ref": "executor.invalid"}),
    ],
)
def test_execution_kinds_reject_missing_or_incompatible_fields(
    execution_kind: str,
    remove: str,
    add: dict[str, Any],
) -> None:
    catalog = load_catalog()
    node = copy.deepcopy(node_by_key(catalog, "lesson_plan.generate"))
    node["execution_kind"] = execution_kind
    node.pop(remove, None)
    node.update(add)
    catalog["nodes"] = [node]

    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")


def test_duplicate_node_keys_are_rejected() -> None:
    catalog = load_catalog()
    catalog["nodes"].append(copy.deepcopy(catalog["nodes"][0]))

    assert_rejected(catalog, "NODE_BINDING_DUPLICATE_NODE_KEY")


def test_context_allow_and_forbid_sets_cannot_overlap() -> None:
    catalog = load_catalog()
    policy = node_by_key(catalog, "lesson.division.generate")["context_policy"]
    policy["forbidden_sources"] = ["material.approved_parse"]

    assert_rejected(catalog, "NODE_BINDING_CONTEXT_CONFLICT")


def test_instruction_refs_and_reference_roles_must_be_unique() -> None:
    catalog = load_catalog()
    instructions = node_by_key(catalog, "lesson_plan.generate")["instruction_policy"]
    instructions["refs"].append(copy.deepcopy(instructions["refs"][0]))
    assert_rejected(catalog, "NODE_BINDING_INSTRUCTION_REF_DUPLICATE")

    catalog = load_catalog()
    policy = node_by_key(catalog, "video.shots.generate")["reference_asset_policy"]
    policy["roles"].append(copy.deepcopy(policy["roles"][0]))
    assert_rejected(catalog, "NODE_BINDING_REFERENCE_ROLE_DUPLICATE")


def test_reference_asset_cardinality_and_mode_are_enforced() -> None:
    catalog = load_catalog()
    role = node_by_key(catalog, "video.shots.generate")["reference_asset_policy"]["roles"][0]
    role["min_items"] = 2
    role["max_items"] = 1
    assert_rejected(catalog, "NODE_BINDING_REFERENCE_CARDINALITY_INVALID")

    catalog = load_catalog()
    policy = node_by_key(catalog, "video.shots.generate")["reference_asset_policy"]
    for role in policy["roles"]:
        role["requirement"] = "optional"
        role["min_items"] = 0
    assert_rejected(catalog, "NODE_BINDING_REFERENCE_POLICY_INVALID")

    catalog = load_catalog()
    policy = node_by_key(catalog, "ppt.cover.image.generate")["reference_asset_policy"]
    policy["roles"][0]["requirement"] = "required"
    policy["roles"][0]["min_items"] = 1
    assert_rejected(catalog, "NODE_BINDING_REFERENCE_POLICY_INVALID")


@pytest.mark.parametrize(
    ("node_key", "field", "value", "code"),
    [
        (
            "lesson_plan.generate",
            "model_capability",
            "text.gpt-4o",
            "NODE_BINDING_CAPABILITY_FORBIDDEN",
        ),
        (
            "material.parse",
            "executor_ref",
            "executor.powershell",
            "NODE_BINDING_EXECUTOR_FORBIDDEN",
        ),
    ],
)
def test_provider_models_and_dangerous_executors_are_rejected(
    node_key: str,
    field: str,
    value: str,
    code: str,
) -> None:
    catalog = load_catalog()
    node_by_key(catalog, node_key)[field] = value

    assert_rejected(catalog, code)


@pytest.mark.parametrize(
    ("node_key", "teacher_surface"),
    [
        ("material.parse", "editable"),
        ("lesson_plan.generate", "not_applicable"),
    ],
)
def test_prompt_exposure_matches_execution_kind(
    node_key: str,
    teacher_surface: str,
) -> None:
    catalog = load_catalog()
    node_by_key(catalog, node_key)["prompt_exposure_policy"]["teacher_business_prompt"] = (
        teacher_surface
    )

    assert_rejected(catalog, "NODE_BINDING_PROMPT_EXPOSURE_INVALID")


def test_human_gate_must_block_downstream_execution() -> None:
    catalog = load_catalog()
    node_by_key(catalog, "lesson_plan.approve")["approval_policy"]["required_before_downstream"] = (
        False
    )

    assert_rejected(catalog, "NODE_BINDING_HUMAN_GATE_INVALID")


@pytest.mark.parametrize(
    ("node_key", "field", "value"),
    [
        ("material.parse", "executor_ref", "https://example.invalid/run"),
        ("lesson_plan.generate", "model_capability", "https://example.invalid/model"),
    ],
)
def test_external_urls_and_paths_are_rejected_by_schema(
    node_key: str,
    field: str,
    value: str,
) -> None:
    catalog = load_catalog()
    node_by_key(catalog, node_key)[field] = value

    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")


def test_instruction_reference_cannot_be_a_path() -> None:
    catalog = load_catalog()
    node_by_key(catalog, "lesson_plan.generate")["instruction_policy"]["refs"][0]["content_key"] = (
        "../private.md"
    )

    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")


def test_cli_validates_catalog_and_reports_stable_errors(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(CLI_PATH), str(FIXTURE_PATH)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert "primary_math.courseware" in result.stdout
    assert "nodes" in result.stdout

    invalid = load_catalog()
    node_by_key(invalid, "lesson_plan.generate")["model_capability"] = "text.gpt-4o"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
    rejected = subprocess.run(
        [sys.executable, str(CLI_PATH), str(invalid_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert rejected.returncode == 2
    assert rejected.stderr.startswith("NODE_BINDING_CAPABILITY_FORBIDDEN:")
