"""Declarative workflow registry with deterministic contract resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from workflow.definition import (
    WorkflowDefinitionError,
    WorkflowGraph,
    WorkflowNodeDefinition,
    validate_workflow_graph,
)


@dataclass(frozen=True, slots=True)
class RegisteredWorkflow:
    graph: WorkflowGraph
    topological_order: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowRegistry:
    available_contract_refs: frozenset[str]

    def load(self, payload: dict[str, Any]) -> RegisteredWorkflow:
        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list):
            raise WorkflowDefinitionError("workflow graph nodes must be an array")
        nodes = tuple(self._parse_node(raw) for raw in cast(list[object], raw_nodes))
        graph = WorkflowGraph(nodes=nodes)
        order = validate_workflow_graph(
            graph,
            available_contract_refs=self.available_contract_refs,
        )
        return RegisteredWorkflow(graph=graph, topological_order=order)

    @staticmethod
    def _parse_node(raw: object) -> WorkflowNodeDefinition:
        if not isinstance(raw, dict):
            raise WorkflowDefinitionError("workflow nodes must be objects")
        values = cast(dict[str, object], raw)
        node_key = values.get("node_key")
        branch_key = values.get("branch_key")
        if not isinstance(node_key, str):
            raise WorkflowDefinitionError("workflow node_key must be a string")
        if branch_key is not None and not isinstance(branch_key, str):
            raise WorkflowDefinitionError("workflow branch_key must be a string or null")
        dependencies = WorkflowRegistry._parse_string_array(values, "dependencies")
        input_refs = WorkflowRegistry._parse_string_array(values, "input_contract_refs")
        output_refs = WorkflowRegistry._parse_string_array(values, "output_contract_refs")
        return WorkflowNodeDefinition(
            node_key=node_key,
            branch_key=branch_key,
            dependencies=dependencies,
            input_contract_refs=input_refs,
            output_contract_refs=output_refs,
        )

    @staticmethod
    def _parse_string_array(values: dict[str, object], name: str) -> tuple[str, ...]:
        raw = values.get(name, [])
        if not isinstance(raw, list):
            raise WorkflowDefinitionError(f"workflow node {name} must be a string array")
        items = cast(list[object], raw)
        if not all(isinstance(value, str) for value in items):
            raise WorkflowDefinitionError(f"workflow node {name} must be a string array")
        return tuple(cast(list[str], items))


BUILTIN_WORKFLOW_REGISTRY = WorkflowRegistry(
    available_contract_refs=frozenset({"content:lesson_plan"})
)
