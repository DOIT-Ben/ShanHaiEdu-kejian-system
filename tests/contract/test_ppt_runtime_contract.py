from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from workflow.content_package import validate_content_package
from workflow.node_generation_binding import (
    NodeGenerationBindingError,
    validate_workflow_node_catalog,
)
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
CATALOG_PATH = CONTRACTS / "fixtures/workflow-node-generation-bindings/primary-math-courseware.json"
SCHEMA_PATH = CONTRACTS / "workflow-node-generation-binding.schema.json"
SOURCE_PATH = ROOT / "workflow/builtin/primary_math_courseware/generation-source.json"
PACKAGE_PATH = CONTRACTS / "fixtures/primary-math-courseware-package"


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _node(catalog: dict[str, Any], key: str) -> dict[str, Any]:
    return next(node for node in catalog["nodes"] if node["node_key"] == key)


def _assert_rejected(catalog: dict[str, Any], code: str) -> None:
    with pytest.raises(NodeGenerationBindingError) as caught:
        validate_workflow_node_catalog(catalog, schema=_object(SCHEMA_PATH))
    assert caught.value.code == code


def test_current_release_preserves_both_ppt_deterministic_outputs() -> None:
    catalog = _object(CATALOG_PATH)
    source = _object(SOURCE_PATH)
    package = validate_content_package(PACKAGE_PATH, contracts_root=CONTRACTS)
    registered = BUILTIN_WORKFLOW_REGISTRY.load(catalog)

    assert catalog["semantic_version"] == "1.4.0"
    assert source["package"]["semantic_version"] == "1.4.0"
    assert {item["output_key"] for item in source["deterministic_outputs"]} == {
        "ppt.pages.assemble.output",
        "pptx.export.output",
    }
    assert {
        key
        for key, item in package.items.items()
        if item["kind"] == "content_definition"
        and key in {"ppt.pages.assemble.output", "pptx.export.output"}
    } == {"ppt.pages.assemble.output", "pptx.export.output"}

    assemble = _node(catalog, "ppt.pages.assemble")
    export = _node(catalog, "pptx.export")
    assert assemble["output_persistence"]["artifact"] == {
        "identity": {
            "strategy": "lesson_unit_singleton",
            "artifact_key_prefix": "ppt-page-previews",
        },
        "artifact_type": "ppt_page_previews",
        "branch_key": "ppt",
        "content_definition_ref": {
            "item_key": "ppt.pages.assemble.output",
            "kind": "content_definition",
        },
        "content": {"source": "output", "pointer": ""},
        "relations": [
            {
                "source_binding": "artifact:ppt_page_specs",
                "relation_type": "derives_from",
                "binding_key": "upstream.artifact.ppt_page_specs",
                "impact_scope": {"mode": "all"},
            }
        ],
    }
    assert export["output_persistence"]["artifact"] == {
        "identity": {
            "strategy": "lesson_unit_singleton",
            "artifact_key_prefix": "ppt-final",
        },
        "artifact_type": "ppt_final",
        "branch_key": "ppt",
        "content_definition_ref": {
            "item_key": "pptx.export.output",
            "kind": "content_definition",
        },
        "content": {"source": "output", "pointer": ""},
        "relations": [
            {
                "source_binding": "artifact:ppt_page_previews",
                "relation_type": "derives_from",
                "binding_key": "upstream.artifact.ppt_page_previews",
                "impact_scope": {"mode": "all"},
            },
            {
                "source_binding": "artifact:ppt_page_specs",
                "relation_type": "derives_from",
                "binding_key": "upstream.artifact.ppt_page_specs",
                "impact_scope": {"mode": "all"},
            },
        ],
    }
    assert export["output_persistence"]["quality_source_binding"] == "linked_file_asset"
    assert export["output_persistence"]["approval_completion"] == {
        "kind": "workflow_gate",
        "source_input_ref": "asset:pptx",
    }

    assert len(registered.output_definition_index) == 25
    assemble_index = registered.output_definition_index["ppt.pages.assemble.output"]
    export_index = registered.output_definition_index["pptx.export.output"]
    assert assemble_index.producer_node_key == "ppt.pages.assemble"
    assert assemble_index.generation_template_key is None
    assert export_index.producer_node_key == "pptx.export"
    assert export_index.generation_template_key is None
    assert export_index.quality_validate_node_key == "ppt.final.validate"
    assert export_index.quality_gate_node_key == "ppt.final.approve"
    assert export_index.quality_source_binding == "linked_file_asset"


def test_quality_gated_outputs_require_an_explicit_supported_source_binding() -> None:
    catalog = _object(CATALOG_PATH)
    expected = {
        "lesson.division.generate": "artifact",
        "lesson_plan.generate": "artifact",
        "intro.generate_options": "artifact",
        "pptx.export": "linked_file_asset",
    }
    assert {
        node_key: _node(catalog, node_key)["output_persistence"]["quality_source_binding"]
        for node_key in expected
    } == expected

    missing = copy.deepcopy(catalog)
    _node(missing, "pptx.export")["output_persistence"].pop("quality_source_binding")
    _assert_rejected(missing, "NODE_BINDING_QUALITY_SOURCE_BINDING_INVALID")

    unknown = copy.deepcopy(catalog)
    _node(unknown, "pptx.export")["output_persistence"]["quality_source_binding"] = "guessed"
    _assert_rejected(unknown, "NODE_BINDING_SCHEMA_INVALID")


def test_deterministic_output_persistence_is_narrowly_limited_to_declared_executor_nodes() -> None:
    catalog = _object(CATALOG_PATH)
    invalid = copy.deepcopy(catalog)
    source = _node(invalid, "ppt.pages.assemble")
    _node(invalid, "material.parse")["output_persistence"] = copy.deepcopy(
        source["output_persistence"]
    )

    _assert_rejected(invalid, "NODE_BINDING_DETERMINISTIC_OUTPUT_INVALID")
