from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from workflow.definition import WorkflowDefinitionError
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = (
    ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"
)


def load_catalog() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


def minimal_v2_catalog() -> dict[str, Any]:
    return {
        "api_version": "shanhai.workflow-node-generation-binding/v2",
        "catalog_key": "test.workflow",
        "workflow_key": "test.workflow",
        "semantic_version": "1.1.0",
        "external_input_contract_refs": ["input:custom"],
        "validator_descriptors": [
            {
                "key": "validator.test",
                "semantic_version": "1.0.0",
                "implementation_digest": "a" * 64,
                "implementation_status": "contract_only",
            }
        ],
        "nodes": [
            {
                "node_key": "prepare",
                "title": "Prepare",
                "phase": "material",
                "execution_kind": "deterministic",
                "execution_scope": "project",
                "branch_key": "material",
                "entrypoint": True,
                "dependencies": [],
                "executor_ref": "executor.test.prepare",
                "input_contract_refs": ["input:custom"],
                "output_contract_refs": ["artifact:custom"],
                "validator_refs": [],
                "prompt_exposure_policy": {},
                "instruction_policy": {},
                "context_policy": {},
                "reference_asset_policy": {},
                "repair_policy": {},
                "approval_policy": {},
                "output_persistence": {"artifact": {"artifact_type": "test"}},
            },
            {
                "node_key": "finish",
                "title": "Finish",
                "phase": "material",
                "execution_kind": "deterministic",
                "execution_scope": "project",
                "branch_key": "material",
                "entrypoint": False,
                "dependencies": ["prepare"],
                "executor_ref": "executor.test.finish",
                "input_contract_refs": ["artifact:custom"],
                "output_contract_refs": ["report:custom"],
                "validator_refs": [],
                "prompt_exposure_policy": {},
                "instruction_policy": {},
                "context_policy": {},
                "reference_asset_policy": {},
                "repair_policy": {},
                "approval_policy": {},
            },
        ],
    }


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


def test_registry_reads_legacy_release_without_granting_v2_projection_capabilities() -> None:
    legacy = {
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

    registered = BUILTIN_WORKFLOW_REGISTRY.load(legacy)

    assert registered.topological_order == ("generate",)
    assert registered.node_by_key["generate"].binding == legacy["nodes"][0]
    assert registered.output_definition_index == {}


@pytest.mark.parametrize(
    "mutate",
    (
        lambda catalog: catalog["nodes"][0].pop("execution_scope"),
        lambda catalog: catalog["nodes"][0].pop("entrypoint"),
        lambda catalog: catalog["nodes"][1].update(dependencies=["missing.node"]),
    ),
)
def test_registry_rejects_incomplete_v2_catalog(mutate) -> None:
    catalog = copy.deepcopy(load_catalog())
    mutate(catalog)

    with pytest.raises(WorkflowDefinitionError):
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)


def test_registry_uses_catalog_contract_refs_instead_of_a_builtin_allowlist() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(minimal_v2_catalog())

    assert registered.topological_order == ("prepare", "finish")


def test_registered_node_keeps_the_raw_binding_snapshot() -> None:
    catalog = minimal_v2_catalog()
    registered = BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    binding = registered.node_by_key["prepare"].binding
    assert binding == catalog["nodes"][0]
    catalog["nodes"][0]["title"] = "changed after load"
    assert binding["title"] == "Prepare"


def test_registered_indexes_are_immutable() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(load_catalog())

    with pytest.raises(TypeError):
        registered.output_definition_index["new.output"] = object()
    with pytest.raises(TypeError):
        registered.producer_index[("lesson_unit", "ppt", "asset:new")] = object()


def test_registry_rejects_duplicate_contract_producers_in_one_branch() -> None:
    catalog = minimal_v2_catalog()
    catalog["nodes"][1]["output_contract_refs"] = ["artifact:custom"]

    with pytest.raises(WorkflowDefinitionError) as caught:
        BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert caught.value.code == "WORKFLOW_OUTPUT_PRODUCER_DUPLICATE"
