"""Topology validation for declarative workflow graphs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from workflow.definition import (
    LESSON_UNIT_BRANCH_KEYS,
    PROJECT_BRANCH_KEYS,
    WorkflowDefinitionError,
    WorkflowGraph,
    WorkflowNodeDefinition,
)
from workflow.definition_values import as_mapping


def validate_workflow_graph(
    graph: WorkflowGraph,
    *,
    available_contract_refs: frozenset[str] | None = None,
) -> tuple[str, ...]:
    keys = [node.node_key for node in graph.nodes]
    if len(keys) != len(set(keys)):
        raise WorkflowDefinitionError(
            "workflow graph contains duplicate node_key values",
            code="WORKFLOW_NODE_KEY_DUPLICATE",
        )
    node_by_key = {node.node_key: node for node in graph.nodes}
    for node in graph.nodes:
        _validate_node_shape(node)
        _validate_node_dependencies(node, node_by_key)
        _validate_contract_refs(node, available_contract_refs)

    ordered = _dependency_order(graph.nodes, node_by_key)
    _validate_entrypoint_groups(graph.nodes)
    _validate_input_dependency_closure(graph.nodes, node_by_key)
    return ordered


def _validate_node_shape(node: WorkflowNodeDefinition) -> None:
    if not node.node_key.strip():
        raise WorkflowDefinitionError(
            "workflow node_key cannot be empty",
            code="WORKFLOW_NODE_DECLARATION_INVALID",
        )
    if node.execution_kind not in {"model_generation", "deterministic", "human_gate"}:
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} has an invalid execution kind",
            code="WORKFLOW_NODE_KIND_INVALID",
        )
    if node.execution_scope not in {"project", "lesson_unit"}:
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} has an invalid execution scope",
            code="WORKFLOW_NODE_SCOPE_INVALID",
        )
    if node.execution_scope == "project" and node.branch_key not in PROJECT_BRANCH_KEYS:
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} has an invalid branch for project scope",
            code="WORKFLOW_NODE_BRANCH_INVALID",
        )
    if node.execution_scope == "lesson_unit" and node.branch_key not in LESSON_UNIT_BRANCH_KEYS:
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} has an invalid branch for lesson_unit scope",
            code="WORKFLOW_NODE_BRANCH_INVALID",
        )
    if type(node.entrypoint) is not bool:
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} entrypoint must be a boolean",
            code="WORKFLOW_NODE_ENTRYPOINT_INVALID",
        )


def _validate_node_dependencies(
    node: WorkflowNodeDefinition,
    node_by_key: Mapping[str, WorkflowNodeDefinition],
) -> None:
    if len(node.dependencies) != len(set(node.dependencies)):
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} contains duplicate dependencies",
            code="WORKFLOW_DEPENDENCY_DUPLICATE",
        )
    if any(not dependency.strip() for dependency in node.dependencies):
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} contains an invalid dependency",
            code="WORKFLOW_DEPENDENCY_INVALID",
        )
    missing = set(node.dependencies) - node_by_key.keys()
    if missing:
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} has missing dependencies: {sorted(missing)}",
            code="WORKFLOW_DEPENDENCY_MISSING",
        )
    if node.entrypoint != (not node.dependencies):
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} entrypoint does not match dependencies",
            code="WORKFLOW_ENTRYPOINT_INVALID",
        )
    for dependency in node.dependencies:
        dependency_node = node_by_key[dependency]
        if dependency_node.execution_scope != node.execution_scope:
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} dependency {dependency} crosses execution scope",
                code="WORKFLOW_DEPENDENCY_SCOPE_INVALID",
            )
        if dependency_node.branch_key != node.branch_key:
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} dependency {dependency} crosses branch",
                code="WORKFLOW_DEPENDENCY_BRANCH_INVALID",
            )


def _validate_contract_refs(
    node: WorkflowNodeDefinition,
    available_contract_refs: frozenset[str] | None,
) -> None:
    if available_contract_refs is None:
        return
    referenced = set(node.input_contract_refs) | set(node.output_contract_refs)
    missing_contracts = referenced - available_contract_refs
    if missing_contracts:
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} has missing contract refs: {sorted(missing_contracts)}",
            code="WORKFLOW_CONTRACT_REF_MISSING",
        )


def _dependency_order(
    nodes: tuple[WorkflowNodeDefinition, ...],
    node_by_key: Mapping[str, WorkflowNodeDefinition],
) -> tuple[str, ...]:
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_key: str) -> None:
        if node_key in visited:
            return
        if node_key in visiting:
            raise WorkflowDefinitionError(
                "workflow graph contains a dependency cycle",
                code="WORKFLOW_DEPENDENCY_CYCLE",
            )
        visiting.add(node_key)
        for dependency in node_by_key[node_key].dependencies:
            visit(dependency)
        visiting.remove(node_key)
        visited.add(node_key)
        ordered.append(node_key)

    for node in nodes:
        visit(node.node_key)
    return tuple(ordered)


def _validate_entrypoint_groups(nodes: tuple[WorkflowNodeDefinition, ...]) -> None:
    groups: dict[tuple[str, str], list[WorkflowNodeDefinition]] = defaultdict(list)
    for node in nodes:
        if not isinstance(node.branch_key, str):
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has no concrete branch key",
                code="WORKFLOW_NODE_BRANCH_INVALID",
            )
        groups[(node.execution_scope, node.branch_key)].append(node)
    for (scope, branch), members in groups.items():
        entries = [node.node_key for node in members if node.entrypoint]
        if len(entries) != 1:
            raise WorkflowDefinitionError(
                f"workflow group {scope}/{branch} must have exactly one entrypoint; "
                f"found {entries}",
                code="WORKFLOW_ENTRYPOINT_GROUP_INVALID",
            )


def _validate_input_dependency_closure(
    nodes: tuple[WorkflowNodeDefinition, ...],
    node_by_key: Mapping[str, WorkflowNodeDefinition],
) -> None:
    producers, producers_by_contract = _input_producers(nodes)
    closure_by_node: dict[str, frozenset[str]] = {}
    for node in nodes:
        closure = _dependency_closure(node.node_key, node_by_key, closure_by_node)
        for input_ref in node.input_contract_refs:
            _validate_input_dependency(
                node,
                input_ref,
                closure,
                producers,
                producers_by_contract,
            )


def _input_producers(
    nodes: tuple[WorkflowNodeDefinition, ...],
) -> tuple[
    dict[tuple[str, str | None, str], list[str]],
    dict[str, list[str]],
]:
    producers: dict[tuple[str, str | None, str], list[str]] = defaultdict(list)
    producers_by_contract: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        for output_ref in node.output_contract_refs:
            producers[(node.execution_scope, node.branch_key, output_ref)].append(node.node_key)
            producers_by_contract[output_ref].append(node.node_key)
    return producers, producers_by_contract


def _dependency_closure(
    node_key: str,
    node_by_key: Mapping[str, WorkflowNodeDefinition],
    closure_by_node: dict[str, frozenset[str]],
) -> frozenset[str]:
    cached = closure_by_node.get(node_key)
    if cached is not None:
        return cached
    closure: set[str] = set()
    for dependency in node_by_key[node_key].dependencies:
        closure.add(dependency)
        closure.update(_dependency_closure(dependency, node_by_key, closure_by_node))
    result = frozenset(closure)
    closure_by_node[node_key] = result
    return result


def _validate_input_dependency(
    node: WorkflowNodeDefinition,
    input_ref: str,
    closure: frozenset[str],
    producers: Mapping[tuple[str, str | None, str], list[str]],
    producers_by_contract: Mapping[str, list[str]],
) -> None:
    matches = producers.get((node.execution_scope, node.branch_key, input_ref), [])
    global_matches = producers_by_contract.get(input_ref, [])
    if len(matches) > 1:
        raise WorkflowDefinitionError(
            f"contract {input_ref} has multiple producers in "
            f"{node.execution_scope}/{node.branch_key}",
            code="WORKFLOW_OUTPUT_PRODUCER_DUPLICATE",
        )
    if not matches and len(global_matches) > 1:
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} has an ambiguous cross-branch "
            f"input producer for {input_ref}",
            code="WORKFLOW_INPUT_PRODUCER_AMBIGUOUS",
        )
    if matches and matches[0] not in closure:
        code = "WORKFLOW_INPUT_DEPENDENCY_MISSING"
        binding = as_mapping(node.binding)
        requirement = as_mapping(
            binding.get("quality_requirement") if binding is not None else None
        )
        if node.execution_kind == "human_gate" and requirement is not None:
            code = "WORKFLOW_OUTPUT_QUALITY_GATE_INVALID"
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} consumes {input_ref} before its "
            f"producer {matches[0]} is in the dependency closure",
            code=code,
        )
