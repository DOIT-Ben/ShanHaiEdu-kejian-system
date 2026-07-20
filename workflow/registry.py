"""Declarative workflow registry with deterministic contract resolution."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast

from workflow.definition import (
    WorkflowDefinitionError,
    WorkflowGraph,
    WorkflowIndexes,
    WorkflowNodeDefinition,
    WorkflowOutputDefinitionBinding,
    WorkflowProducerRef,
    build_workflow_indexes,
    validate_workflow_graph,
)

WORKFLOW_CATALOG_API_VERSION = "shanhai.workflow-node-generation-binding/v2"


@dataclass(frozen=True, slots=True)
class RegisteredWorkflow:
    graph: WorkflowGraph
    topological_order: tuple[str, ...]
    node_by_key: Mapping[str, WorkflowNodeDefinition]
    producers_by_contract: Mapping[str, tuple[WorkflowProducerRef, ...]]
    producer_index: Mapping[tuple[str, str, str], WorkflowProducerRef]
    output_definition_index: Mapping[str, WorkflowOutputDefinitionBinding]

    @property
    def indexes(self) -> WorkflowIndexes:
        """Return the immutable derived indexes as one value object."""

        return WorkflowIndexes(
            producers_by_contract=self.producers_by_contract,
            producer_index=self.producer_index,
            output_definition_index=self.output_definition_index,
        )


@dataclass(frozen=True, slots=True)
class WorkflowRegistry:
    """Parse the published graph shape without embedding business contracts.

    Contract references are supplied by the catalog itself: external inputs at the
    root and produced references on nodes.  The registry therefore remains useful
    for every published workflow rather than silently accepting one built-in list.
    """

    available_contract_refs: frozenset[str] | None = None

    def load(self, payload: dict[str, Any]) -> RegisteredWorkflow:
        if "api_version" not in payload:
            return self._load_legacy(payload)
        self._require_v2_catalog(payload)
        external_refs = self._parse_string_array(
            payload,
            "external_input_contract_refs",
            required=True,
            error_code="WORKFLOW_CATALOG_DECLARATION_INVALID",
        )
        raw_descriptors = payload.get("validator_descriptors")
        if not isinstance(raw_descriptors, list):
            raise WorkflowDefinitionError(
                "workflow catalog validator_descriptors must be an array",
                code="WORKFLOW_CATALOG_DECLARATION_INVALID",
            )
        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list):
            raise WorkflowDefinitionError(
                "workflow graph nodes must be an array",
                code="WORKFLOW_CATALOG_DECLARATION_INVALID",
            )
        nodes = tuple(self._parse_node(raw) for raw in cast(list[object], raw_nodes))
        graph = WorkflowGraph(nodes=nodes)
        produced_refs = frozenset(
            output_ref for node in nodes for output_ref in node.output_contract_refs
        )
        available_refs = set(external_refs) | set(produced_refs)
        if self.available_contract_refs is not None:
            available_refs.update(self.available_contract_refs)
        order = validate_workflow_graph(
            graph,
            available_contract_refs=frozenset(available_refs),
        )
        indexes = build_workflow_indexes(graph)
        node_by_key = MappingProxyType({node.node_key: node for node in nodes})
        return RegisteredWorkflow(
            graph=graph,
            topological_order=order,
            node_by_key=node_by_key,
            producers_by_contract=indexes.producers_by_contract,
            producer_index=indexes.producer_index,
            output_definition_index=indexes.output_definition_index,
        )

    def _load_legacy(self, payload: Mapping[str, object]) -> RegisteredWorkflow:
        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list):
            raise WorkflowDefinitionError(
                "legacy workflow graph nodes must be an array",
                code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            )
        nodes = tuple(self._parse_legacy_node(raw) for raw in cast(list[object], raw_nodes))
        graph = WorkflowGraph(nodes=nodes)
        node_by_key = {node.node_key: node for node in nodes}
        if len(node_by_key) != len(nodes):
            raise WorkflowDefinitionError(
                "legacy workflow graph contains duplicate node_key values",
                code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            )
        return RegisteredWorkflow(
            graph=graph,
            topological_order=self._legacy_topological_order(node_by_key),
            node_by_key=MappingProxyType(node_by_key),
            producers_by_contract=MappingProxyType({}),
            producer_index=MappingProxyType({}),
            output_definition_index=MappingProxyType({}),
        )

    @staticmethod
    def _parse_legacy_node(raw: object) -> WorkflowNodeDefinition:
        if not isinstance(raw, dict):
            raise WorkflowDefinitionError(
                "legacy workflow nodes must be objects",
                code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            )
        values = cast(dict[str, object], raw)
        node_key = values.get("node_key")
        if not isinstance(node_key, str) or not node_key.strip():
            raise WorkflowDefinitionError(
                "legacy workflow node_key must be a non-empty string",
                code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            )
        branch_key = values.get("branch_key")
        if branch_key is not None and not isinstance(branch_key, str):
            raise WorkflowDefinitionError(
                "legacy workflow branch_key must be a string or null",
                code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            )
        dependencies = WorkflowRegistry._parse_string_array(
            values, "dependencies", required=True, error_code="WORKFLOW_LEGACY_DECLARATION_INVALID"
        )
        return WorkflowNodeDefinition(
            node_key=node_key,
            execution_kind="deterministic",
            execution_scope="project",
            branch_key=branch_key,
            entrypoint=not dependencies,
            dependencies=dependencies,
            input_contract_refs=WorkflowRegistry._parse_string_array(
                values,
                "input_contract_refs",
                required=True,
                error_code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            ),
            output_contract_refs=WorkflowRegistry._parse_string_array(
                values,
                "output_contract_refs",
                required=True,
                error_code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            ),
            binding=copy.deepcopy(values),
        )

    @staticmethod
    def _legacy_topological_order(
        nodes: Mapping[str, WorkflowNodeDefinition],
    ) -> tuple[str, ...]:
        ordered: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_key: str) -> None:
            if node_key in visited:
                return
            if node_key in visiting:
                raise WorkflowDefinitionError(
                    "legacy workflow graph contains a dependency cycle",
                    code="WORKFLOW_LEGACY_DECLARATION_INVALID",
                )
            node = nodes.get(node_key)
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

        for node_key in nodes:
            visit(node_key)
        return tuple(ordered)

    @staticmethod
    def _require_v2_catalog(payload: Mapping[str, object]) -> None:
        if payload.get("api_version") != WORKFLOW_CATALOG_API_VERSION:
            raise WorkflowDefinitionError(
                "unsupported release: workflow catalog must use the v2 declaration",
                code="WORKFLOW_RELEASE_UNSUPPORTED",
            )

    @staticmethod
    def _parse_node(raw: object) -> WorkflowNodeDefinition:
        if not isinstance(raw, dict):
            raise WorkflowDefinitionError(
                "workflow nodes must be objects",
                code="WORKFLOW_NODE_DECLARATION_INVALID",
            )
        values = cast(dict[str, object], raw)
        required = (
            "node_key",
            "execution_kind",
            "execution_scope",
            "branch_key",
            "entrypoint",
            "dependencies",
            "input_contract_refs",
            "output_contract_refs",
        )
        missing = [name for name in required if name not in values]
        if missing:
            raise WorkflowDefinitionError(
                f"workflow node declaration is missing fields: {sorted(missing)}",
                code="WORKFLOW_NODE_DECLARATION_INVALID",
            )
        node_key = values["node_key"]
        execution_scope = values["execution_scope"]
        execution_kind = values["execution_kind"]
        branch_key = values["branch_key"]
        entrypoint = values["entrypoint"]
        if not isinstance(node_key, str):
            raise WorkflowDefinitionError(
                "workflow node_key must be a string",
                code="WORKFLOW_NODE_DECLARATION_INVALID",
            )
        if not isinstance(execution_scope, str):
            raise WorkflowDefinitionError(
                "workflow execution_scope must be a string",
                code="WORKFLOW_NODE_DECLARATION_INVALID",
            )
        if not isinstance(execution_kind, str):
            raise WorkflowDefinitionError(
                "workflow execution_kind must be a string",
                code="WORKFLOW_NODE_DECLARATION_INVALID",
            )
        if branch_key is not None and not isinstance(branch_key, str):
            raise WorkflowDefinitionError(
                "workflow branch_key must be a string or null",
                code="WORKFLOW_NODE_DECLARATION_INVALID",
            )
        if type(entrypoint) is not bool:
            raise WorkflowDefinitionError(
                "workflow entrypoint must be a boolean",
                code="WORKFLOW_NODE_DECLARATION_INVALID",
            )
        dependencies = WorkflowRegistry._parse_string_array(
            values,
            "dependencies",
            required=True,
            error_code="WORKFLOW_NODE_DECLARATION_INVALID",
        )
        input_refs = WorkflowRegistry._parse_string_array(
            values,
            "input_contract_refs",
            required=True,
            error_code="WORKFLOW_NODE_DECLARATION_INVALID",
        )
        output_refs = WorkflowRegistry._parse_string_array(
            values,
            "output_contract_refs",
            required=True,
            error_code="WORKFLOW_NODE_DECLARATION_INVALID",
        )
        return WorkflowNodeDefinition(
            node_key=node_key,
            execution_kind=execution_kind,
            execution_scope=execution_scope,
            branch_key=branch_key,
            entrypoint=entrypoint,
            dependencies=dependencies,
            input_contract_refs=input_refs,
            output_contract_refs=output_refs,
            binding=copy.deepcopy(values),
        )

    @staticmethod
    def _parse_string_array(
        values: Mapping[str, object],
        name: str,
        *,
        required: bool = False,
        error_code: str = "WORKFLOW_NODE_DECLARATION_INVALID",
    ) -> tuple[str, ...]:
        if name not in values and not required:
            return ()
        raw = values.get(name)
        if not isinstance(raw, list):
            raise WorkflowDefinitionError(
                f"workflow node {name} must be a string array",
                code=error_code,
            )
        items = cast(list[object], raw)
        if not all(isinstance(value, str) for value in items):
            raise WorkflowDefinitionError(
                f"workflow node {name} must be a string array",
                code=error_code,
            )
        return tuple(cast(list[str], items))


BUILTIN_WORKFLOW_REGISTRY = WorkflowRegistry()
