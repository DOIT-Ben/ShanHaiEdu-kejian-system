"""Declarative workflow registry with deterministic contract resolution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    freeze_workflow_value,
    validate_workflow_graph,
)
from workflow.node_generation_binding import (
    NodeGenerationBindingError,
    validate_workflow_node_catalog_semantics,
)

WORKFLOW_CATALOG_API_VERSION = "shanhai.workflow-node-generation-binding/v2"
LEGACY_WORKFLOW_CATALOG_API_VERSION = "shanhai.workflow-node-generation-binding/v1"


@dataclass(frozen=True, slots=True)
class RegisteredWorkflow:
    graph: WorkflowGraph
    topological_order: tuple[str, ...]
    node_by_key: Mapping[str, WorkflowNodeDefinition]
    producers_by_contract: Mapping[str, tuple[WorkflowProducerRef, ...]]
    producer_index: Mapping[tuple[str, str, str], WorkflowProducerRef]
    output_definition_index: Mapping[str, WorkflowOutputDefinitionBinding]
    validator_descriptor_index: Mapping[tuple[str, str], Mapping[str, Any]]
    supports_output_projection: bool = True

    @property
    def indexes(self) -> WorkflowIndexes:
        """Return the immutable derived indexes as one value object."""

        return WorkflowIndexes(
            producers_by_contract=self.producers_by_contract,
            producer_index=self.producer_index,
            output_definition_index=self.output_definition_index,
        )

    def require_output_projection(self) -> None:
        if not self.supports_output_projection:
            raise WorkflowDefinitionError(
                "unsupported release: legacy workflow has no output projection contract",
                code="WORKFLOW_RELEASE_UNSUPPORTED",
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
        api_version = payload.get("api_version")
        if api_version != WORKFLOW_CATALOG_API_VERSION:
            if api_version == LEGACY_WORKFLOW_CATALOG_API_VERSION or api_version is None:
                return self._load_legacy(payload)
            raise WorkflowDefinitionError(
                "unsupported release: workflow catalog must use a supported declaration",
                code="WORKFLOW_RELEASE_UNSUPPORTED",
            )
        external_refs = self._parse_string_array(
            payload,
            "external_input_contract_refs",
            required=True,
            error_code="WORKFLOW_CATALOG_DECLARATION_INVALID",
        )
        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list):
            raise WorkflowDefinitionError(
                "workflow graph nodes must be an array",
                code="WORKFLOW_CATALOG_DECLARATION_INVALID",
            )
        nodes = tuple(self._parse_node(raw) for raw in cast(list[object], raw_nodes))
        validator_index = self._parse_validator_descriptors(payload)
        self._validate_node_validator_refs(nodes, validator_index)
        indexes = self._validate_v2_semantics(payload)
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
        node_by_key = MappingProxyType({node.node_key: node for node in nodes})
        return RegisteredWorkflow(
            graph=graph,
            topological_order=order,
            node_by_key=node_by_key,
            producers_by_contract=indexes.producers_by_contract,
            producer_index=indexes.producer_index,
            output_definition_index=indexes.output_definition_index,
            validator_descriptor_index=validator_index,
        )

    @staticmethod
    def _validate_v2_semantics(payload: dict[str, Any]) -> WorkflowIndexes:
        try:
            return validate_workflow_node_catalog_semantics(payload)
        except NodeGenerationBindingError as exc:
            suffix = exc.code.removeprefix("NODE_BINDING_")
            suffix = {
                "DUPLICATE_NODE_KEY": "NODE_KEY_DUPLICATE",
                "CONTRACT_REF_UNRESOLVED": "CONTRACT_REF_MISSING",
            }.get(suffix, suffix)
            raise WorkflowDefinitionError(str(exc), code=f"WORKFLOW_{suffix}") from exc
        except (AttributeError, KeyError, TypeError) as exc:
            raise WorkflowDefinitionError(
                "workflow catalog semantic declaration is invalid",
                code="WORKFLOW_CATALOG_DECLARATION_INVALID",
            ) from exc

    def _load_legacy(self, payload: Mapping[str, object]) -> RegisteredWorkflow:
        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list):
            raise WorkflowDefinitionError(
                "legacy workflow graph nodes must be an array",
                code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            )
        nodes = tuple(self._parse_legacy_node(raw) for raw in cast(list[object], raw_nodes))
        order = self._legacy_topological_order(nodes)
        empty: Mapping[str, Any] = MappingProxyType({})
        return RegisteredWorkflow(
            graph=WorkflowGraph(nodes=nodes),
            topological_order=order,
            node_by_key=MappingProxyType({node.node_key: node for node in nodes}),
            producers_by_contract=empty,
            producer_index=MappingProxyType({}),
            output_definition_index=MappingProxyType({}),
            validator_descriptor_index=MappingProxyType({}),
            supports_output_projection=False,
        )

    @staticmethod
    def _parse_validator_descriptors(
        payload: Mapping[str, object],
    ) -> Mapping[tuple[str, str], Mapping[str, Any]]:
        raw_descriptors = payload.get("validator_descriptors")
        if not isinstance(raw_descriptors, list):
            raise WorkflowDefinitionError(
                "workflow catalog validator_descriptors must be an array",
                code="WORKFLOW_CATALOG_DECLARATION_INVALID",
            )
        if not raw_descriptors:
            raise WorkflowDefinitionError(
                "workflow catalog validator_descriptors cannot be empty",
                code="WORKFLOW_VALIDATOR_DESCRIPTOR_INVALID",
            )
        descriptors: dict[tuple[str, str], Mapping[str, Any]] = {}
        for raw in cast(list[object], raw_descriptors):
            if not isinstance(raw, dict):
                raise WorkflowDefinitionError(
                    "workflow validator descriptors must be objects",
                    code="WORKFLOW_VALIDATOR_DESCRIPTOR_INVALID",
                )
            descriptor = cast(dict[str, object], raw)
            key = descriptor.get("key")
            version = descriptor.get("semantic_version")
            digest = descriptor.get("implementation_digest")
            status = descriptor.get("implementation_status")
            if (
                type(key) is not str
                or not key.strip()
                or type(version) is not str
                or not version.strip()
                or type(digest) is not str
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
                or digest == "0" * 64
                or status != "contract_only"
            ):
                raise WorkflowDefinitionError(
                    "workflow validator descriptor is invalid",
                    code="WORKFLOW_VALIDATOR_DESCRIPTOR_INVALID",
                )
            identity = (key, version)
            prior = descriptors.get(identity)
            if prior is not None:
                if prior["implementation_digest"] != digest:
                    raise WorkflowDefinitionError(
                        f"workflow validator descriptor conflicts: {key}",
                        code="WORKFLOW_VALIDATOR_DESCRIPTOR_CONFLICT",
                    )
                raise WorkflowDefinitionError(
                    f"workflow validator descriptor is duplicated: {key}",
                    code="WORKFLOW_VALIDATOR_DESCRIPTOR_DUPLICATE",
                )
            frozen = freeze_workflow_value(descriptor)
            assert isinstance(frozen, Mapping)
            descriptors[identity] = cast(Mapping[str, Any], frozen)
        return MappingProxyType(descriptors)

    @staticmethod
    def _validate_node_validator_refs(
        nodes: tuple[WorkflowNodeDefinition, ...],
        descriptors: Mapping[tuple[str, str], Mapping[str, Any]],
    ) -> None:
        for node in nodes:
            binding = node.binding
            refs = binding.get("validator_refs")
            if not isinstance(refs, (list, tuple)):
                raise WorkflowDefinitionError(
                    f"workflow node {node.node_key} has invalid validator refs",
                    code="WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED",
                )
            all_refs = list(cast(Sequence[object], refs))
            report = binding.get("quality_report_persistence")
            if isinstance(report, Mapping):
                report_refs = report.get("validator_refs")
                if not isinstance(report_refs, (list, tuple)):
                    raise WorkflowDefinitionError(
                        f"workflow node {node.node_key} has invalid validator refs",
                        code="WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED",
                    )
                all_refs.extend(cast(Sequence[object], report_refs))
            for ref in all_refs:
                if not isinstance(ref, Mapping):
                    raise WorkflowDefinitionError(
                        f"workflow node {node.node_key} has invalid validator ref",
                        code="WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED",
                    )
                values = cast(Mapping[str, object], ref)
                key = values.get("key")
                version = values.get("semantic_version")
                digest = values.get("implementation_digest")
                if type(key) is not str or type(version) is not str or type(digest) is not str:
                    raise WorkflowDefinitionError(
                        f"workflow node {node.node_key} has unresolved validator ref",
                        code="WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED",
                    )
                descriptor = descriptors.get((key, version))
                if descriptor is None or descriptor["implementation_digest"] != digest:
                    raise WorkflowDefinitionError(
                        f"workflow node {node.node_key} has unresolved validator ref",
                        code="WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED",
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
        if type(node_key) is not str or not node_key.strip():
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
        execution_kind = values.get("execution_kind", "deterministic")
        if type(execution_kind) is not str or not execution_kind.strip():
            raise WorkflowDefinitionError(
                "legacy workflow execution_kind must be a non-empty string",
                code="WORKFLOW_LEGACY_DECLARATION_INVALID",
            )
        dependencies = WorkflowRegistry._parse_string_array(
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
            branch_key=cast(str | None, branch_key),
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
            binding=cast(Mapping[str, Any], frozen),
        )

    @staticmethod
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
            binding=cast(Mapping[str, Any], freeze_workflow_value(values)),
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
