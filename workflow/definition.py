"""Declarative workflow graph definitions and publication validation."""

from __future__ import annotations

from dataclasses import dataclass


class WorkflowDefinitionError(ValueError):
    """Raised when a workflow graph cannot be safely published."""


@dataclass(frozen=True, slots=True)
class WorkflowNodeDefinition:
    node_key: str
    branch_key: str | None
    dependencies: tuple[str, ...]
    input_contract_refs: tuple[str, ...]
    output_contract_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowGraph:
    nodes: tuple[WorkflowNodeDefinition, ...]


def validate_workflow_graph(
    graph: WorkflowGraph,
    *,
    available_contract_refs: frozenset[str] | None = None,
) -> tuple[str, ...]:
    keys = [node.node_key for node in graph.nodes]
    if len(keys) != len(set(keys)):
        raise WorkflowDefinitionError("workflow graph contains duplicate node_key values")
    node_by_key = {node.node_key: node for node in graph.nodes}
    for node in graph.nodes:
        if not node.node_key.strip():
            raise WorkflowDefinitionError("workflow node_key cannot be empty")
        missing = set(node.dependencies) - node_by_key.keys()
        if missing:
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has missing dependencies: {sorted(missing)}"
            )
        if available_contract_refs is not None:
            referenced = set(node.input_contract_refs) | set(node.output_contract_refs)
            missing_contracts = referenced - available_contract_refs
            if missing_contracts:
                raise WorkflowDefinitionError(
                    f"workflow node {node.node_key} has missing contract refs: "
                    f"{sorted(missing_contracts)}"
                )

    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_key: str) -> None:
        if node_key in visited:
            return
        if node_key in visiting:
            raise WorkflowDefinitionError("workflow graph contains a dependency cycle")
        visiting.add(node_key)
        for dependency in node_by_key[node_key].dependencies:
            visit(dependency)
        visiting.remove(node_key)
        visited.add(node_key)
        ordered.append(node_key)

    for node in graph.nodes:
        visit(node.node_key)
    return tuple(ordered)
