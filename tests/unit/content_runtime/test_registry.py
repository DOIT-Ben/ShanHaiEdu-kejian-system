from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from workflow.definition import WorkflowDefinitionError
from workflow.node_generation_binding import validate_workflow_node_catalog
from workflow.registry import (
    BUILTIN_WORKFLOW_REGISTRY,
    LEGACY_WORKFLOW_CATALOG_API_VERSION,
)

ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = (
    ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"
)
SCHEMA_PATH = ROOT / "contracts/workflow-node-generation-binding.schema.json"


def load_catalog() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


def load_schema() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def minimal_v2_catalog() -> dict[str, Any]:
    catalog = copy.deepcopy(load_catalog())
    node_keys = {
        "material.file_validate",
        "material.parse",
        "material.scope_review",
    }
    catalog["catalog_key"] = "test.material"
    catalog["workflow_key"] = "test.material"
    catalog["nodes"] = [node for node in catalog["nodes"] if node["node_key"] in node_keys]
    referenced_validators = {
        (
            ref["key"],
            ref["semantic_version"],
            ref["implementation_digest"],
        )
        for node in catalog["nodes"]
        for ref in node["validator_refs"]
    }
    catalog["validator_descriptors"] = [
        descriptor
        for descriptor in catalog["validator_descriptors"]
        if (
            descriptor["key"],
            descriptor["semantic_version"],
            descriptor["implementation_digest"],
        )
        in referenced_validators
    ]
    return catalog


def test_minimal_v2_catalog_is_a_valid_published_contract() -> None:
    validated = validate_workflow_node_catalog(
        minimal_v2_catalog(),
        schema=load_schema(),
    )

    assert len(validated.catalog["nodes"]) == 3


def test_registry_loads_the_published_catalog_with_one_deterministic_order() -> None:
    catalog = load_catalog()

    registered = BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert len(registered.graph.nodes) == 47
    assert len(registered.topological_order) == 47
    assert set(registered.topological_order) == {node["node_key"] for node in catalog["nodes"]}
    lesson_plan = registered.node_by_key["lesson_plan.generate"]
    assert lesson_plan.execution_scope == "lesson_unit"
    assert lesson_plan.branch_key == "lesson_plan"
    assert lesson_plan.entrypoint is True
    assert lesson_plan.dependencies == ()
    assert lesson_plan.binding["output_persistence"]
    assert len(registered.output_definition_index) == 22
    assert registered.output_definition_index is registered.indexes.output_definition_index
    assert {
        producer.node_key for producer in registered.producers_by_contract["asset:image_candidates"]
    } == {
        "ppt.cover.image.generate",
        "video.style_master.image.generate",
    }
    assert registered.require_output_projection() is None


@pytest.mark.parametrize("explicit_version", (False, True))
def test_registry_loads_legacy_graph_but_rejects_output_projection(
    explicit_version: bool,
) -> None:
    legacy: dict[str, Any] = {
        "nodes": [
            {
                "node_key": "generate",
                "branch_key": "lesson_plan",
                "dependencies": [],
                "input_contract_refs": ["content:lesson_plan"],
                "output_contract_refs": [],
            }
        ]
    }
    if explicit_version:
        legacy["api_version"] = LEGACY_WORKFLOW_CATALOG_API_VERSION

    registered = BUILTIN_WORKFLOW_REGISTRY.load(legacy)

    assert registered.topological_order == ("generate",)
    assert registered.supports_output_projection is False
    assert not registered.producer_index
    assert not registered.output_definition_index
    assert not registered.validator_descriptor_index
    with pytest.raises(WorkflowDefinitionError, match="unsupported release") as caught:
        registered.require_output_projection()
    assert caught.value.code == "WORKFLOW_RELEASE_UNSUPPORTED"


def test_registry_rejects_unknown_catalog_version() -> None:
    catalog = minimal_v2_catalog()
    catalog["api_version"] = "shanhai.workflow-node-generation-binding/v999"

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert caught.value.code == "WORKFLOW_RELEASE_UNSUPPORTED"


@pytest.mark.parametrize("field", ("execution_scope", "entrypoint"))
def test_registry_rejects_incomplete_v2_catalog(field: str) -> None:
    catalog = copy.deepcopy(load_catalog())
    catalog["nodes"][0].pop(field)

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert caught.value.code == "WORKFLOW_NODE_DECLARATION_INVALID"


def test_registry_rejects_a_missing_dependency() -> None:
    catalog = copy.deepcopy(load_catalog())
    catalog["nodes"][1]["dependencies"] = ["missing.node"]

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert caught.value.code == "WORKFLOW_DEPENDENCY_MISSING"


def test_registry_rejects_an_internal_input_outside_the_dependency_closure() -> None:
    catalog = load_catalog()
    node = next(
        item for item in catalog["nodes"] if item["node_key"] == "ppt.cover.prompt.generate"
    )
    node["dependencies"] = ["ppt.outline.approve"]

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)
    assert caught.value.code == "WORKFLOW_INPUT_DEPENDENCY_MISSING"


def test_registry_rejects_ambiguous_cross_branch_inputs() -> None:
    catalog = load_catalog()
    node = next(item for item in catalog["nodes"] if item["node_key"] == "delivery.package")
    node["input_contract_refs"].append("package:creation_image")

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)
    assert caught.value.code == "WORKFLOW_INPUT_PRODUCER_AMBIGUOUS"


def test_registry_rejects_external_inputs_that_alias_published_outputs() -> None:
    catalog = load_catalog()
    catalog["external_input_contract_refs"].append("approval:lesson_plan")

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)
    assert caught.value.code == "WORKFLOW_EXTERNAL_CONTRACT_COLLISION"


def test_registry_rejects_non_root_artifact_content_projection() -> None:
    catalog = load_catalog()
    node = next(item for item in catalog["nodes"] if item["node_key"] == "ppt.outline.generate")
    node["output_persistence"]["artifact"]["content"] = {
        "source": "constant",
        "value": {},
    }

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)
    assert caught.value.code == "WORKFLOW_ARTIFACT_CONTENT_INVALID"


def test_registry_rejects_missing_same_branch_model_relation() -> None:
    catalog = load_catalog()
    node = next(
        item for item in catalog["nodes"] if item["node_key"] == "ppt.cover.prompt.generate"
    )
    relations = node["output_persistence"]["artifact"]["relations"]
    relations[:] = [
        relation
        for relation in relations
        if relation["source_binding"] != "artifact:ppt_page_specs"
    ]

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)
    assert caught.value.code == "WORKFLOW_RELATION_SOURCE_MISSING"


def test_registry_rejects_an_unusable_target_slot_prefix() -> None:
    catalog = load_catalog()
    node = next(
        item for item in catalog["nodes"] if item["node_key"] == "ppt.body_asset_prompts.generate"
    )
    node["output_persistence"]["creation_package"]["target_rules"]["target_slot_prefix"] = (
        f"{'a' * 159}."
    )

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)
    assert caught.value.code == "WORKFLOW_TARGET_SLOT_PREFIX_INVALID"


def test_registry_rejects_a_gate_that_consumes_another_contract() -> None:
    catalog = load_catalog()
    node = next(item for item in catalog["nodes"] if item["node_key"] == "ppt.outline.approve")
    node["input_contract_refs"] = ["approval:lesson_plan"]

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)
    assert caught.value.code == "WORKFLOW_OUTPUT_QUALITY_GATE_INVALID"


def test_registry_uses_catalog_contract_refs_instead_of_a_builtin_allowlist() -> None:
    catalog = minimal_v2_catalog()
    catalog["external_input_contract_refs"] = ["content:lesson_plan", "input:custom"]
    for node in catalog["nodes"]:
        node["input_contract_refs"] = [
            "input:custom" if ref == "material:file_asset" else ref
            for ref in node["input_contract_refs"]
        ]

    registered = BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert registered.topological_order == (
        "material.file_validate",
        "material.parse",
        "material.scope_review",
    )


def test_registered_node_keeps_the_frozen_binding_snapshot() -> None:
    catalog = minimal_v2_catalog()
    registered = BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    binding = registered.node_by_key["material.parse"].binding
    original_title = binding["title"]
    assert binding["dependencies"] == ("material.file_validate",)
    assert binding["output_contract_refs"] == ("content:material_evidence",)
    catalog["nodes"][1]["title"] = "changed after load"
    catalog["nodes"][1]["instruction_policy"]["refs"][0]["role"] = "changed"
    assert binding["title"] == original_title
    assert binding["instruction_policy"]["refs"][0]["role"] == "quality"


def test_registered_binding_is_recursively_immutable() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(load_catalog())
    binding = registered.node_by_key["lesson_plan.generate"].binding
    artifact = cast(dict[str, Any], binding["output_persistence"])["artifact"]
    validator_refs = cast(tuple[dict[str, Any], ...], binding["validator_refs"])

    with pytest.raises(TypeError):
        cast(dict[str, Any], binding)["title"] = "changed"
    with pytest.raises(TypeError):
        cast(dict[str, Any], artifact)["artifact_type"] = "changed"
    with pytest.raises(TypeError):
        validator_refs[0]["key"] = "changed"
    with pytest.raises(TypeError):
        dict.__setitem__(binding, "title", "changed")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        dict.__setitem__(artifact, "artifact_type", "changed")  # type: ignore[arg-type]
    assert isinstance(binding["output_contract_refs"], tuple)
    assert isinstance(binding["validator_refs"], tuple)


def test_registered_indexes_are_immutable() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(load_catalog())

    with pytest.raises(TypeError):
        cast(dict[str, object], registered.output_definition_index)["new.output"] = object()
    with pytest.raises(TypeError):
        cast(dict[tuple[str, str, str], object], registered.producer_index)[
            ("lesson_unit", "ppt", "asset:new")
        ] = object()


def test_registry_rejects_duplicate_contract_producers_in_one_branch() -> None:
    catalog = minimal_v2_catalog()
    catalog["nodes"][1]["output_contract_refs"] = [
        "content:material_evidence",
        "report:file_validation",
    ]

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert caught.value.code == "WORKFLOW_OUTPUT_PRODUCER_DUPLICATE"


def test_registry_rejects_output_persistence_on_a_deterministic_node() -> None:
    catalog = minimal_v2_catalog()
    source = load_catalog()
    model_node = next(
        node for node in source["nodes"] if node["node_key"] == "lesson.division.generate"
    )
    persistence = copy.deepcopy(model_node["output_persistence"])
    persistence["artifact"]["relations"] = []
    catalog["nodes"][1]["output_persistence"] = persistence

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert caught.value.code == "WORKFLOW_EXECUTION_KIND_INVALID"


def test_registry_builds_an_immutable_validator_descriptor_index() -> None:
    catalog = load_catalog()
    registered = BUILTIN_WORKFLOW_REGISTRY.load(catalog)
    descriptor = catalog["validator_descriptors"][0]
    identity = (
        descriptor["key"],
        descriptor["semantic_version"],
    )

    assert len(registered.validator_descriptor_index) == len(catalog["validator_descriptors"])
    assert (
        registered.validator_descriptor_index[identity]["implementation_status"] == "contract_only"
    )
    catalog["validator_descriptors"][0]["implementation_status"] = "changed"
    assert (
        registered.validator_descriptor_index[identity]["implementation_status"] == "contract_only"
    )
    with pytest.raises(TypeError):
        cast(dict[str, Any], registered.validator_descriptor_index[identity])["key"] = "changed"
    with pytest.raises(TypeError):
        cast(dict[tuple[str, str], object], registered.validator_descriptor_index)[
            ("validator.changed", "1.0.0")
        ] = object()


def test_registry_rejects_empty_validator_descriptor_catalog() -> None:
    catalog = load_catalog()
    catalog["validator_descriptors"] = []

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert caught.value.code == "WORKFLOW_VALIDATOR_DESCRIPTOR_INVALID"


@pytest.mark.parametrize("reference_location", ("node", "report", "gate"))
def test_registry_rejects_validator_reference_digest_drift(
    reference_location: str,
) -> None:
    catalog = load_catalog()
    nodes = cast(list[dict[str, Any]], catalog["nodes"])
    if reference_location == "report":
        node = next(item for item in nodes if "quality_report_persistence" in item)
        refs = cast(
            list[dict[str, Any]],
            node["quality_report_persistence"]["validator_refs"],
        )
    else:
        execution_kind = "human_gate" if reference_location == "gate" else "model_generation"
        node = next(
            item
            for item in nodes
            if item["execution_kind"] == execution_kind and item["validator_refs"]
        )
        refs = cast(list[dict[str, Any]], node["validator_refs"])
    refs[0]["implementation_digest"] = "b" * 64

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert caught.value.code == "WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED"
