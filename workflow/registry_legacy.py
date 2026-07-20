"""Legacy workflow registry loader retained for published release compatibility."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

from workflow.definition import (
    WorkflowDefinitionError,
    WorkflowGraph,
    WorkflowNodeDefinition,
    WorkflowOutputDefinitionBinding,
    WorkflowProducerRef,
    freeze_workflow_value,
)
from workflow.registry_parsing import ValidatorDescriptorIndex, parse_string_array
from workflow.registry_runtime import RegisteredWorkflow


def load_legacy_workflow(payload: Mapping[str, object]) -> RegisteredWorkflow:
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list):
        raise WorkflowDefinitionError(
            "legacy workflow graph nodes must be an array",
            code="WORKFLOW_LEGACY_DECLARATION_INVALID",
        )
    nodes = tuple(_parse_legacy_node(raw) for raw in cast(list[object], raw_nodes))
    return RegisteredWorkflow(
        graph=WorkflowGraph(nodes=nodes),
        topological_order=_legacy_topological_order(nodes),
        node_by_key=MappingProxyType({node.node_key: node for node in nodes}),
        producers_by_contract=_empty_producers(),
        producer_index=_empty_producer_index(),
        output_definition_index=_empty_output_index(),
        validator_descriptor_index=_empty_validator_index(),
        supports_output_projection=False,
    )


def _empty_producers() -> Mapping[str, tuple[WorkflowProducerRef, ...]]:
    return MappingProxyType({})


def _empty_producer_index() -> Mapping[tuple[str, str, str], WorkflowProducerRef]:
    return MappingProxyType({})


def _empty_output_index() -> Mapping[str, WorkflowOutputDefinitionBinding]:
    return MappingProxyType({})


def _empty_validator_index() -> ValidatorDescriptorIndex:
    return MappingProxyType({})


def _parse_legacy_node(raw: object) -> WorkflowNodeDefinition:
    values = _parse_legacy_mapping(raw)
    node_key = _parse_legacy_node_key(values)
    branch_key = _parse_legacy_branch_key(values)
    execution_kind = _parse_legacy_execution_kind(values)
    dependencies = parse_string_array(
        values,
        "dependencies",
        error_code="WORKFLOW_LEGACY_DECLARATION_INVALID",
    )
    frozen = freeze_workflow_value(values)
    assert isinstance(frozen, Mapping)
    return WorkflowNodeDefinition(
        node_key=node_key,
        execution_kind=execution_kind,
        execution_scope="legacy",
        branch_key=branch_key,
        entrypoint=not dependencies,
        dependencies=dependencies,
        input_contract_refs=parse_string_array(
            values,
            "input_contract_refs",
            required=True,
            error_code="WORKFLOW_LEGACY_DECLARATION_INVALID",
        ),
        output_contract_refs=parse_string_array(
            values,
            "output_contract_refs",
            required=True,
            error_code="WORKFLOW_LEGACY_DECLARATION_INVALID",
        ),
        binding=cast(Mapping[str, Any], frozen),
    )


def _parse_legacy_mapping(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise WorkflowDefinitionError(
            "legacy workflow nodes must be objects",
            code="WORKFLOW_LEGACY_DECLARATION_INVALID",
        )
    return cast(dict[str, object], raw)


def _parse_legacy_node_key(values: Mapping[str, object]) -> str:
    node_key = values.get("node_key")
    if type(node_key) is not str or not node_key.strip():
        raise WorkflowDefinitionError(
            "legacy workflow node_key must be a non-empty string",
            code="WORKFLOW_LEGACY_DECLARATION_INVALID",
        )
    return node_key


def _parse_legacy_branch_key(values: Mapping[str, object]) -> str | None:
    branch_key = values.get("branch_key")
    if branch_key is not None and not isinstance(branch_key, str):
        raise WorkflowDefinitionError(
            "legacy workflow branch_key must be a string or null",
            code="WORKFLOW_LEGACY_DECLARATION_INVALID",
        )
    return branch_key


def _parse_legacy_execution_kind(values: Mapping[str, object]) -> str:
    execution_kind = values.get("execution_kind", "deterministic")
    if type(execution_kind) is not str or not execution_kind.strip():
        raise WorkflowDefinitionError(
            "legacy workflow execution_kind must be a non-empty string",
            code="WORKFLOW_LEGACY_DECLARATION_INVALID",
        )
    return execution_kind


def _legacy_topological_order(
    nodes: tuple[WorkflowNodeDefinition, ...],
) -> tuple[str, ...]:
    node_by_key = {node.node_key: node for node in nodes}
    if len(node_by_key) != len(nodes):
        raise WorkflowDefinitionError(
            "legacy workflow graph contains duplicate node_key values",
            code="WORKFLOW_LEGACY_DECLARATION_INVALID",
        )
    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[str] = []

    def visit(node_key: str) -> None:
        if node_key in visited:
            return
        if node_key in visiting:
            raise WorkflowDefinitionError(
                "legacy workflow graph contains a dependency cycle",
                code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            )
        node = node_by_key.get(node_key)
        if node is None:
            raise WorkflowDefinitionError(
                f"legacy workflow has missing dependency: {node_key}",
                code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            )
        visiting.add(node_key)
        for dependency in node.dependencies:
            visit(dependency)
        visiting.remove(node_key)
        visited.add(node_key)
        ordered.append(node_key)

    for node in nodes:
        visit(node.node_key)
    return tuple(ordered)
