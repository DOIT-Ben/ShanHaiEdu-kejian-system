from __future__ import annotations

from pathlib import Path

from apps.api.content_runtime.package_source import load_builtin_courseware_release
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[2]


def test_material_scope_has_a_published_human_gate_artifact_contract() -> None:
    source = load_builtin_courseware_release(ROOT)

    assert source.semantic_version == "1.4.0"
    definition = source.items["material.scope_review.output"]
    assert definition["kind"] == "content_definition"
    assert definition["spec"]["definition_key"] == "material.scope_review.output"

    registered = BUILTIN_WORKFLOW_REGISTRY.load(source.workflow_catalog)
    output = registered.output_definition_index["material.scope_review.output"]
    assert output.producer_node_key == "material.scope_review"
    assert output.generation_template_key is None
    assert output.artifact_type == "material_scope"
    assert output.artifact_branch_key == "project"
    assert output.quality_requirement_mode == "none"
