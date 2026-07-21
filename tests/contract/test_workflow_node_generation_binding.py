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
    validate_workflow_node_catalog_semantics,
)
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY


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


def validator_keys(refs: list[dict[str, Any]]) -> set[str]:
    return {cast(str, ref["key"]) for ref in refs}


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
    assert catalog["api_version"] == "shanhai.workflow-node-generation-binding/v2"
    assert catalog["semantic_version"] == "1.1.0"
    assert len(node_keys) == 47
    assert {
        "project": 7,
        "lesson_unit": 40,
    } == {
        scope: sum(node["execution_scope"] == scope for node in catalog["nodes"])
        for scope in ("project", "lesson_unit")
    }
    assert {
        "model_generation": 22,
        "deterministic": 13,
        "human_gate": 12,
    } == {
        kind: sum(node["execution_kind"] == kind for node in catalog["nodes"])
        for kind in ("model_generation", "deterministic", "human_gate")
    }
    assert all(
        {"execution_scope", "branch_key", "entrypoint", "dependencies"} <= node.keys()
        for node in catalog["nodes"]
    )
    assert sum("output_persistence" in node for node in catalog["nodes"]) == 22
    assert all(
        ("output_persistence" in node) == (node["execution_kind"] == "model_generation")
        for node in catalog["nodes"]
    )
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
    assert len(validated.indexes.output_definition_index) == 22
    lesson_plan_index = validated.indexes.output_definition_index["lesson_plan.generate.output"]
    assert lesson_plan_index.producer_node_key == "lesson_plan.generate"
    assert lesson_plan_index.quality_validate_node_key == "lesson_plan.validate"
    assert lesson_plan_index.quality_gate_node_key == "lesson_plan.approve"
    assert lesson_plan_index.quality_requirement_mode == "reports"
    for contract_ref, expected in {
        "prompt:image_request": {
            "ppt.cover.prompt.generate",
            "video.style_master.prompt.generate",
        },
        "asset:image_candidates": {
            "ppt.cover.image.generate",
            "video.style_master.image.generate",
        },
        "package:creation_image": {
            "ppt.body_asset_prompts.generate",
            "video.asset_prompts.generate",
        },
    }.items():
        assert {
            producer.node_key for producer in validated.indexes.producers_by_contract[contract_ref]
        } == expected

    registered = BUILTIN_WORKFLOW_REGISTRY.load(catalog)
    assert registered.indexes == validated.indexes


def test_catalog_declares_versioned_validator_descriptors() -> None:
    catalog = load_catalog()
    descriptors = catalog["validator_descriptors"]
    identities = {
        (item["key"], item["semantic_version"], item["implementation_digest"])
        for item in descriptors
    }

    assert len(descriptors) == 68
    assert len(identities) == len(descriptors)
    assert all(len(item["implementation_digest"]) == 64 for item in descriptors)
    assert all(
        {"key", "semantic_version", "implementation_digest"} <= ref.keys()
        for node in catalog["nodes"]
        for ref in node["validator_refs"]
    )


def test_catalog_declares_final_ppt_and_video_quality_chains() -> None:
    catalog = load_catalog()
    output_mapping = {
        "conclusion": {"source": "output", "pointer": "/conclusion"},
        "findings": {"source": "output", "pointer": "/findings"},
        "evidence": {"source": "output", "pointer": "/evidence"},
    }

    ppt_validate = node_by_key(catalog, "ppt.final.validate")
    ppt_report = ppt_validate["quality_report_persistence"]
    assert ppt_validate["dependencies"] == ["pptx.export"]
    assert ppt_report == {
        "source_input_ref": "asset:pptx",
        "report_ref": "report:ppt_final_quality",
        "validator_refs": ppt_validate["validator_refs"],
        "mapping": output_mapping,
    }
    assert validator_keys(ppt_validate["validator_refs"]) == {
        "validator.pptx.openable",
        "validator.pptx.render_match",
        "validator.ppt.teaching_scope",
        "validator.ppt.layout",
    }
    ppt_gate = node_by_key(catalog, "ppt.final.approve")
    assert ppt_gate["input_contract_refs"] == ["asset:pptx", "report:ppt_final_quality"]
    assert ppt_gate["dependencies"] == ["pptx.export", "ppt.final.validate"]
    assert ppt_gate["quality_requirement"] == {
        "mode": "reports",
        "report_refs": ["report:ppt_final_quality"],
        "accepted_conclusions": ["passed"],
    }

    classroom = node_by_key(catalog, "video.classroom_quality.evaluate")
    assert classroom["output_contract_refs"] == ["report:video_classroom_quality"]
    assert classroom["dependencies"] == ["video.timeline.assemble"]
    video_validate = node_by_key(catalog, "video.technical.validate")
    video_report = video_validate["quality_report_persistence"]
    assert video_validate["input_contract_refs"] == [
        "asset:video_final",
        "report:video_classroom_quality",
    ]
    assert video_validate["output_contract_refs"] == ["report:video_final_quality"]
    assert video_validate["dependencies"] == [
        "video.timeline.assemble",
        "video.classroom_quality.evaluate",
    ]
    assert video_report == {
        "source_input_ref": "asset:video_final",
        "report_ref": "report:video_final_quality",
        "validator_refs": video_validate["validator_refs"],
        "mapping": output_mapping,
    }
    assert validator_keys(video_validate["validator_refs"]) == {
        "validator.video.file",
        "validator.video.codec",
        "validator.video.duration",
        "validator.video.timeline_sync",
        "validator.video.classroom_quality_schema",
        "validator.video.handoff",
        "validator.video.no_preteach",
    }
    video_gate = node_by_key(catalog, "video.final.approve")
    assert video_gate["input_contract_refs"] == [
        "asset:video_final",
        "report:video_final_quality",
    ]
    assert video_gate["dependencies"] == [
        "video.timeline.assemble",
        "video.technical.validate",
    ]
    assert video_gate["quality_requirement"] == {
        "mode": "reports",
        "report_refs": ["report:video_final_quality"],
        "accepted_conclusions": ["passed"],
    }


def test_catalog_semantics_are_available_without_reloading_the_schema() -> None:
    catalog = load_catalog()

    indexes = validate_workflow_node_catalog_semantics(catalog)

    assert indexes == validate_workflow_node_catalog(catalog, schema=load_schema()).indexes


def test_internal_input_requires_its_producer_in_the_dependency_closure() -> None:
    catalog = load_catalog()
    node_by_key(catalog, "ppt.cover.prompt.generate")["dependencies"] = ["ppt.outline.approve"]

    assert_rejected(catalog, "NODE_BINDING_INPUT_DEPENDENCY_MISSING")
    with pytest.raises(NodeGenerationBindingError) as caught:
        validate_workflow_node_catalog_semantics(catalog)
    assert caught.value.code == "NODE_BINDING_INPUT_DEPENDENCY_MISSING"


def test_cross_branch_input_requires_one_unambiguous_producer() -> None:
    catalog = load_catalog()
    node_by_key(catalog, "delivery.package")["input_contract_refs"].append("package:creation_image")

    assert_rejected(catalog, "NODE_BINDING_INPUT_PRODUCER_AMBIGUOUS")
    with pytest.raises(NodeGenerationBindingError) as caught:
        validate_workflow_node_catalog_semantics(catalog)
    assert caught.value.code == "NODE_BINDING_INPUT_PRODUCER_AMBIGUOUS"


def test_external_inputs_cannot_alias_a_published_output() -> None:
    catalog = load_catalog()
    catalog["external_input_contract_refs"].append("approval:lesson_plan")

    assert_rejected(catalog, "NODE_BINDING_EXTERNAL_CONTRACT_COLLISION")
    with pytest.raises(NodeGenerationBindingError) as caught:
        validate_workflow_node_catalog_semantics(catalog)
    assert caught.value.code == "NODE_BINDING_EXTERNAL_CONTRACT_COLLISION"


def test_direct_gate_cannot_approve_a_different_contract() -> None:
    catalog = load_catalog()
    node_by_key(catalog, "ppt.outline.approve")["input_contract_refs"] = ["approval:lesson_plan"]

    assert_rejected(catalog, "NODE_BINDING_OUTPUT_QUALITY_GATE_INVALID")
    with pytest.raises(NodeGenerationBindingError) as caught:
        validate_workflow_node_catalog_semantics(catalog)
    assert caught.value.code == "NODE_BINDING_OUTPUT_QUALITY_GATE_INVALID"


def test_topology_rejects_missing_cycles_and_implicit_entrypoints() -> None:
    catalog = load_catalog()
    node_by_key(catalog, "lesson_plan.validate")["dependencies"] = ["missing.node"]
    assert_rejected(catalog, "NODE_BINDING_DEPENDENCY_MISSING")

    catalog = load_catalog()
    node_by_key(catalog, "lesson_plan.generate")["dependencies"] = ["lesson_plan.validate"]
    node_by_key(catalog, "lesson_plan.generate")["entrypoint"] = False
    assert_rejected(catalog, "NODE_BINDING_DEPENDENCY_CYCLE")

    catalog = load_catalog()
    node_by_key(catalog, "lesson_plan.generate")["entrypoint"] = False
    assert_rejected(catalog, "NODE_BINDING_ENTRYPOINT_INVALID")


def test_topology_rejects_cross_scope_and_cross_branch_dependencies() -> None:
    catalog = load_catalog()
    node_by_key(catalog, "lesson_plan.generate")["dependencies"] = ["material.scope_review"]
    node_by_key(catalog, "lesson_plan.generate")["entrypoint"] = False
    assert_rejected(catalog, "NODE_BINDING_DEPENDENCY_SCOPE_INVALID")

    catalog = load_catalog()
    node_by_key(catalog, "ppt.content_analyze")["dependencies"] = ["lesson_plan.approve"]
    node_by_key(catalog, "ppt.content_analyze")["entrypoint"] = False
    assert_rejected(catalog, "NODE_BINDING_DEPENDENCY_BRANCH_INVALID")


def test_topology_requires_one_entrypoint_per_scope_branch_group() -> None:
    catalog = load_catalog()
    duplicate = copy.deepcopy(node_by_key(catalog, "material.file_validate"))
    duplicate["node_key"] = "material.file_validate_duplicate"
    duplicate["output_contract_refs"] = ["report:file_validation_duplicate"]
    catalog["nodes"].append(duplicate)

    assert_rejected(catalog, "NODE_BINDING_ENTRYPOINT_GROUP_INVALID")


def test_output_contract_and_content_definition_mappings_are_unambiguous() -> None:
    catalog = load_catalog()
    node_by_key(catalog, "ppt.content_analyze")["output_contract_refs"] = [
        "content:ppt_analysis",
        "artifact:extra",
    ]
    assert_rejected(catalog, "NODE_BINDING_OUTPUT_CONTRACT_AMBIGUOUS")

    catalog = load_catalog()
    node_by_key(catalog, "intro.generate_options")["output_persistence"]["artifact"][
        "content_definition_ref"
    ]["item_key"] = node_by_key(catalog, "lesson_plan.generate")["output_persistence"]["artifact"][
        "content_definition_ref"
    ]["item_key"]
    assert_rejected(catalog, "NODE_BINDING_OUTPUT_DEFINITION_DUPLICATE")


def test_model_artifact_content_must_preserve_the_validated_output_root() -> None:
    catalog = load_catalog()
    node_by_key(catalog, "ppt.outline.generate")["output_persistence"]["artifact"]["content"] = {
        "source": "constant",
        "value": {},
    }

    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")
    with pytest.raises(NodeGenerationBindingError) as caught:
        validate_workflow_node_catalog_semantics(catalog)
    assert caught.value.code == "NODE_BINDING_ARTIFACT_CONTENT_INVALID"


def test_same_branch_model_artifact_input_requires_a_relation_binding() -> None:
    catalog = load_catalog()
    relations = node_by_key(catalog, "ppt.cover.prompt.generate")["output_persistence"]["artifact"][
        "relations"
    ]
    relations[:] = [
        relation
        for relation in relations
        if relation["source_binding"] != "artifact:ppt_page_specs"
    ]

    assert_rejected(catalog, "NODE_BINDING_RELATION_SOURCE_MISSING")
    with pytest.raises(NodeGenerationBindingError) as caught:
        validate_workflow_node_catalog_semantics(catalog)
    assert caught.value.code == "NODE_BINDING_RELATION_SOURCE_MISSING"


def test_quality_gate_report_refs_must_be_unique() -> None:
    catalog = load_catalog()
    requirement = node_by_key(catalog, "lesson_plan.approve")["quality_requirement"]
    requirement["report_refs"].append(requirement["report_refs"][0])

    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")


def test_quality_report_mapping_requires_real_validator_output() -> None:
    catalog = load_catalog()
    mapping = node_by_key(catalog, "lesson_plan.validate")["quality_report_persistence"]["mapping"]
    mapping["conclusion"] = {"source": "constant", "value": "passed"}

    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")


def test_quality_report_validator_set_must_match_the_node() -> None:
    catalog = load_catalog()
    persistence = node_by_key(catalog, "lesson_plan.validate")["quality_report_persistence"]
    persistence["validator_refs"].pop()

    assert_rejected(catalog, "NODE_BINDING_QUALITY_VALIDATOR_INVALID")


def test_video_final_quality_chain_cannot_bypass_the_intermediate_report() -> None:
    catalog = load_catalog()
    validate_node = node_by_key(catalog, "video.technical.validate")
    validate_node["dependencies"].remove("video.classroom_quality.evaluate")

    assert_rejected(catalog, "NODE_BINDING_QUALITY_REPORT_INPUT_INVALID")

    catalog = load_catalog()
    gate = node_by_key(catalog, "video.final.approve")
    gate["input_contract_refs"].append("report:video_classroom_quality")
    gate["dependencies"].append("video.classroom_quality.evaluate")
    gate["quality_requirement"]["report_refs"].append("report:video_classroom_quality")

    assert_rejected(catalog, "NODE_BINDING_QUALITY_REPORT_UNRESOLVED")


def test_output_persistence_forbids_implicit_or_extra_targets() -> None:
    catalog = load_catalog()
    node_by_key(catalog, "lesson_plan.generate").pop("output_persistence")
    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")

    catalog = load_catalog()
    node_by_key(catalog, "lesson_plan.validate")["output_persistence"] = copy.deepcopy(
        node_by_key(catalog, "lesson_plan.generate")["output_persistence"]
    )
    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")

    catalog = load_catalog()
    relation = node_by_key(catalog, "lesson_plan.generate")["output_persistence"]["artifact"][
        "relations"
    ][0]
    relation["to_artifact_version_id"] = "00000000-0000-0000-0000-000000000000"
    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")

    catalog = load_catalog()
    package_node = node_by_key(catalog, "ppt.body_asset_prompts.generate")
    package_node["output_persistence"]["artifact"]["content"] = {
        "source": "output",
        "pointer": "/body_asset_items",
    }
    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")
    with pytest.raises(NodeGenerationBindingError) as caught:
        validate_workflow_node_catalog_semantics(catalog)
    assert caught.value.code == "NODE_BINDING_ARTIFACT_CONTENT_INVALID"


def test_lesson_division_declares_approval_completion_without_runtime_inference() -> None:
    catalog = load_catalog()
    persistence = node_by_key(catalog, "lesson.division.generate")["output_persistence"]

    assert persistence["approval_completion"] == {
        "kind": "lesson_unit_sync",
        "collection_pointer": "/lesson_units",
        "stable_key_field": "lesson_unit_key",
    }

    persistence["approval_completion"]["stable_key_field"] = "id"
    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")


def test_semantic_validator_rejects_reference_asset_schema_bypasses() -> None:
    catalog = load_catalog()
    mapping = node_by_key(catalog, "ppt.body_asset_prompts.generate")["output_persistence"][
        "creation_package"
    ]["item_mapping"]
    mapping["reference_assets"] = {
        "source": "constant",
        "value": [
            {
                "asset_version_id": "00000000-0000-4000-8000-000000000001",
                "role": "style",
            }
        ],
    }

    with pytest.raises(NodeGenerationBindingError) as caught:
        validate_workflow_node_catalog_semantics(catalog)
    assert caught.value.code == "NODE_BINDING_REFERENCE_ASSETS_INVALID"


def test_output_persistence_string_bounds_match_runtime_dtos() -> None:
    catalog = load_catalog()
    max_contract_ref = f"{'a' * 79}:{'b' * 80}"
    node_by_key(catalog, "material.file_validate")["output_contract_refs"][0] = max_contract_ref
    node_by_key(catalog, "material.parse")["input_contract_refs"][1] = max_contract_ref
    lesson_artifact = node_by_key(catalog, "lesson_plan.generate")["output_persistence"]["artifact"]
    lesson_artifact["identity"]["artifact_key_prefix"] = "a" * 79
    lesson_artifact["artifact_type"] = "a" * 80
    package = node_by_key(catalog, "ppt.body_asset_prompts.generate")["output_persistence"][
        "creation_package"
    ]
    package["package_key"]["prefix"] = "a" * 120
    package["target_rules"]["target_slot_prefix"] = f"{'a' * 158}."

    validate_workflow_node_catalog(catalog, schema=load_schema())

    catalog = load_catalog()
    oversized_contract_ref = f"{'a' * 80}:{'b' * 80}"
    node_by_key(catalog, "material.file_validate")["output_contract_refs"][0] = (
        oversized_contract_ref
    )
    node_by_key(catalog, "material.parse")["input_contract_refs"][1] = oversized_contract_ref
    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")

    catalog = load_catalog()
    node_by_key(catalog, "lesson_plan.generate")["output_persistence"]["artifact"]["identity"][
        "artifact_key_prefix"
    ] = "a" * 80
    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")

    catalog = load_catalog()
    node_by_key(catalog, "lesson_plan.generate")["output_persistence"]["artifact"][
        "artifact_type"
    ] = "a" * 81
    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")

    catalog = load_catalog()
    package = node_by_key(catalog, "ppt.body_asset_prompts.generate")["output_persistence"][
        "creation_package"
    ]
    package["package_key"]["prefix"] = "a" * 121
    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")

    catalog = load_catalog()
    package = node_by_key(catalog, "ppt.body_asset_prompts.generate")["output_persistence"][
        "creation_package"
    ]
    package["target_rules"]["target_slot_prefix"] = f"{'a' * 159}."
    assert_rejected(catalog, "NODE_BINDING_SCHEMA_INVALID")


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
        "345e58e9b08f1ec4dd78fe385f155054178cb746b2fdf106d0ea45255fdd802a"
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
