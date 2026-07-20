from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from apps.api.assets.execution_port import AssetExecutionPortError, SqlAlchemyAssetPort
from apps.api.node_execution.boundaries import (
    NodeExecutionBoundaryError,
    validate_execution_boundary,
)
from apps.api.runtime_boundary.ports import (
    RuntimeNodeDefinition,
    WorkflowExecutionContext,
)

RELEASE_ID = UUID("10000000-0000-4000-8000-000000000001")
WORKFLOW_ID = UUID("10000000-0000-4000-8000-000000000002")
PROJECT_ID = UUID("10000000-0000-4000-8000-000000000003")
WORKFLOW_RUN_ID = UUID("10000000-0000-4000-8000-000000000004")
NODE_RUN_ID = UUID("10000000-0000-4000-8000-000000000005")
LESSON_UNIT_ID = UUID("10000000-0000-4000-8000-000000000006")
CONTENT_DEFINITION_ID = UUID("10000000-0000-4000-8000-000000000007")


def definition() -> RuntimeNodeDefinition:
    return RuntimeNodeDefinition(
        content_release_id=RELEASE_ID,
        workflow_definition_version_id=WORKFLOW_ID,
        node_key="lesson_plan.generate",
        execution_kind="model_generation",
        generation_template_key="lesson_plan.generate",
        generation_template={
            "kind": "generation_template",
            "metadata": {"key": "lesson_plan.generate"},
            "spec": {"template_key": "lesson_plan.generate"},
        },
        node_binding={
            "node_key": "lesson_plan.generate",
            "execution_kind": "model_generation",
            "execution_scope": "lesson_unit",
            "branch_key": "lesson_plan",
            "generation_template_ref": {
                "item_key": "lesson_plan.generate",
                "kind": "generation_template",
            },
            "output_persistence": {"artifact": {}},
        },
        content_definition_version_id=CONTENT_DEFINITION_ID,
        content_definition_release_id=RELEASE_ID,
        content_definition_item_key="lesson_plan.generate.output",
    )


def execution() -> WorkflowExecutionContext:
    return WorkflowExecutionContext(
        organization_id=UUID("10000000-0000-4000-8000-000000000010"),
        project_id=PROJECT_ID,
        workflow_run_id=WORKFLOW_RUN_ID,
        node_run_id=NODE_RUN_ID,
        content_release_id=RELEASE_ID,
        workflow_definition_version_id=WORKFLOW_ID,
        node_key="lesson_plan.generate",
        branch_key="lesson_plan",
        lesson_key="lesson-01",
        lesson_unit_id=LESSON_UNIT_ID,
        status="ready",
    )


def test_accepts_one_consistent_published_model_node_boundary() -> None:
    validate_execution_boundary(definition(), execution())


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("content_release_id", PROJECT_ID, "NODE_EXECUTION_RELEASE_MISMATCH"),
        (
            "workflow_definition_version_id",
            PROJECT_ID,
            "NODE_EXECUTION_WORKFLOW_MISMATCH",
        ),
        ("node_key", "intro.generate_options", "NODE_EXECUTION_NODE_MISMATCH"),
    ],
)
def test_rejects_execution_context_mismatches_before_model_call(
    field: str,
    value: object,
    code: str,
) -> None:
    with pytest.raises(NodeExecutionBoundaryError) as caught:
        validate_execution_boundary(definition(), replace(execution(), **{field: value}))

    assert caught.value.code == code


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("execution_kind", "NODE_EXECUTION_KIND_UNSUPPORTED"),
        ("binding_node", "NODE_EXECUTION_BINDING_MISMATCH"),
        ("binding_branch", "NODE_EXECUTION_BINDING_MISMATCH"),
        ("binding_scope", "NODE_EXECUTION_BINDING_MISMATCH"),
        ("template_ref", "NODE_EXECUTION_TEMPLATE_MISMATCH"),
        ("template_payload", "NODE_EXECUTION_TEMPLATE_MISMATCH"),
        ("missing_projection", "NODE_EXECUTION_PROJECTION_MISSING"),
    ],
)
def test_rejects_untrusted_or_incomplete_definition_before_model_call(
    mutation: str,
    code: str,
) -> None:
    current = definition()
    binding = dict(current.node_binding)
    template = dict(current.generation_template)
    if mutation == "execution_kind":
        current = replace(current, execution_kind="deterministic")
    elif mutation == "binding_node":
        binding["node_key"] = "other.generate"
    elif mutation == "binding_branch":
        binding["branch_key"] = "video"
    elif mutation == "binding_scope":
        binding["execution_scope"] = "project"
    elif mutation == "template_ref":
        binding["generation_template_ref"] = {
            "item_key": "other.generate",
            "kind": "generation_template",
        }
    elif mutation == "template_payload":
        template["spec"] = {"template_key": "other.generate"}
    else:
        binding.pop("output_persistence")
    current = replace(current, node_binding=binding, generation_template=template)

    with pytest.raises(NodeExecutionBoundaryError) as caught:
        validate_execution_boundary(current, execution())

    assert caught.value.code == code


def test_reference_asset_policy_freezes_empty_or_fails_closed_without_selection() -> None:
    port = object.__new__(SqlAlchemyAssetPort)
    current = definition()
    none_binding = dict(current.node_binding)
    none_binding["reference_asset_policy"] = {"mode": "none", "roles": []}
    assert (
        port.freeze_reference_assets(replace(current, node_binding=none_binding), execution())
        is None
    )

    optional_binding = dict(current.node_binding)
    optional_binding["reference_asset_policy"] = {
        "mode": "optional",
        "roles": [
            {
                "role_key": "style_reference",
                "min_items": 0,
            }
        ],
    }
    authorization = port.freeze_reference_assets(
        replace(current, node_binding=optional_binding), execution()
    )
    assert authorization is not None and authorization.assets == ()

    required_binding = dict(current.node_binding)
    required_binding["reference_asset_policy"] = {
        "mode": "required",
        "roles": [
            {
                "role_key": "style_reference",
                "min_items": 1,
            }
        ],
    }
    with pytest.raises(AssetExecutionPortError) as caught:
        port.freeze_reference_assets(replace(current, node_binding=required_binding), execution())
    assert caught.value.code == "NODE_EXECUTION_REFERENCE_ASSETS_MISSING"
