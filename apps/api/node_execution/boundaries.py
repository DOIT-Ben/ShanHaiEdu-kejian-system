"""Fail-closed checks for release-bound node execution facts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from apps.api.runtime_boundary.ports import RuntimeNodeDefinition, WorkflowExecutionContext


class NodeExecutionBoundaryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_execution_boundary(
    definition: RuntimeNodeDefinition,
    execution: WorkflowExecutionContext,
) -> None:
    """Reject inconsistent published facts before any model invocation."""

    _require_equal(
        definition.content_release_id,
        execution.content_release_id,
        "NODE_EXECUTION_RELEASE_MISMATCH",
    )
    _require_equal(
        definition.workflow_definition_version_id,
        execution.workflow_definition_version_id,
        "NODE_EXECUTION_WORKFLOW_MISMATCH",
    )
    _require_equal(definition.node_key, execution.node_key, "NODE_EXECUTION_NODE_MISMATCH")
    if definition.execution_kind != "model_generation":
        raise NodeExecutionBoundaryError(
            "NODE_EXECUTION_KIND_UNSUPPORTED",
            "the generic executor only accepts published model-generation nodes",
        )
    binding = definition.node_binding
    if not _binding_matches_execution(binding, definition, execution):
        raise NodeExecutionBoundaryError(
            "NODE_EXECUTION_BINDING_MISMATCH",
            "the node binding does not match the fixed execution context",
        )
    _require_template(binding, definition)
    persistence = _as_mapping(binding.get("output_persistence"))
    if persistence is None or _as_mapping(persistence.get("artifact")) is None:
        raise NodeExecutionBoundaryError(
            "NODE_EXECUTION_PROJECTION_MISSING",
            "the published node has no artifact persistence projection",
        )
    if (
        definition.content_definition_release_id != definition.content_release_id
        or not definition.content_definition_item_key
    ):
        raise NodeExecutionBoundaryError(
            "NODE_EXECUTION_CONTENT_DEFINITION_MISMATCH",
            "the output content definition is not fixed to the project release",
        )


def same_fixed_execution(
    current: WorkflowExecutionContext,
    frozen: WorkflowExecutionContext,
) -> bool:
    return (
        current.organization_id == frozen.organization_id
        and current.project_id == frozen.project_id
        and current.workflow_run_id == frozen.workflow_run_id
        and current.node_run_id == frozen.node_run_id
        and current.content_release_id == frozen.content_release_id
        and current.workflow_definition_version_id == frozen.workflow_definition_version_id
        and current.node_key == frozen.node_key
        and current.branch_key == frozen.branch_key
        and current.lesson_key == frozen.lesson_key
        and current.lesson_unit_id == frozen.lesson_unit_id
    )


def _binding_matches_execution(
    binding: Mapping[str, Any],
    definition: RuntimeNodeDefinition,
    execution: WorkflowExecutionContext,
) -> bool:
    scope = binding.get("execution_scope")
    scope_matches = (
        scope == "project" and execution.lesson_unit_id is None and execution.lesson_key is None
    ) or (
        scope == "lesson_unit"
        and execution.lesson_unit_id is not None
        and execution.lesson_key is not None
    )
    return bool(
        binding.get("node_key") == definition.node_key
        and binding.get("execution_kind") == definition.execution_kind
        and binding.get("branch_key") == execution.branch_key
        and scope_matches
    )


def _require_template(
    binding: Mapping[str, Any],
    definition: RuntimeNodeDefinition,
) -> None:
    template_ref = _as_mapping(binding.get("generation_template_ref"))
    template = definition.generation_template
    spec = _as_mapping(template.get("spec"))
    if not (
        template_ref is not None
        and template_ref.get("kind") == "generation_template"
        and template_ref.get("item_key") == definition.generation_template_key
        and spec is not None
        and spec.get("template_key") == definition.generation_template_key
    ):
        raise NodeExecutionBoundaryError(
            "NODE_EXECUTION_TEMPLATE_MISMATCH",
            "the published generation template identity is inconsistent",
        )


def _require_equal(left: object, right: object, code: str) -> None:
    if left != right:
        raise NodeExecutionBoundaryError(code, "fixed runtime facts do not match")


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return cast(Mapping[str, Any], value)
