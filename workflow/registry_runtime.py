"""Runtime assembly for current workflow registry declarations."""

from __future__ import annotations

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
    validate_workflow_graph,
)
from workflow.node_generation_binding import (
    NodeGenerationBindingError,
    validate_workflow_node_catalog_semantics,
)
from workflow.registry_parsing import (
    ValidatorDescriptorIndex,
    parse_node,
    parse_string_array,
    parse_validator_descriptors,
    validate_node_validator_refs,
)


@dataclass(frozen=True, slots=True)
class RegisteredWorkflow:
    graph: WorkflowGraph
    topological_order: tuple[str, ...]
    node_by_key: Mapping[str, WorkflowNodeDefinition]
    producers_by_contract: Mapping[str, tuple[WorkflowProducerRef, ...]]
    producer_index: Mapping[tuple[str, str, str], WorkflowProducerRef]
    output_definition_index: Mapping[str, WorkflowOutputDefinitionBinding]
    validator_descriptor_index: ValidatorDescriptorIndex
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


def load_current_workflow(
    payload: dict[str, Any],
    *,
    available_contract_refs: frozenset[str] | None,
) -> RegisteredWorkflow:
    external_refs = parse_string_array(
        payload,
        "external_input_contract_refs",
        required=True,
        error_code="WORKFLOW_CATALOG_DECLARATION_INVALID",
    )
    nodes = _parse_nodes(payload)
    validator_index = parse_validator_descriptors(payload)
    validate_node_validator_refs(nodes, validator_index)
    indexes = _validate_v2_semantics(payload)
    graph = WorkflowGraph(nodes=nodes)
    order = validate_workflow_graph(
        graph,
        available_contract_refs=_available_refs(nodes, external_refs, available_contract_refs),
    )
    return RegisteredWorkflow(
        graph=graph,
        topological_order=order,
        node_by_key=MappingProxyType({node.node_key: node for node in nodes}),
        producers_by_contract=indexes.producers_by_contract,
        producer_index=indexes.producer_index,
        output_definition_index=indexes.output_definition_index,
        validator_descriptor_index=validator_index,
    )


def _parse_nodes(payload: Mapping[str, object]) -> tuple[WorkflowNodeDefinition, ...]:
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list):
        raise WorkflowDefinitionError(
            "workflow graph nodes must be an array",
            code="WORKFLOW_CATALOG_DECLARATION_INVALID",
        )
    return tuple(parse_node(raw) for raw in cast(list[object], raw_nodes))


def _available_refs(
    nodes: tuple[WorkflowNodeDefinition, ...],
    external_refs: tuple[str, ...],
    configured_refs: frozenset[str] | None,
) -> frozenset[str]:
    produced_refs = {output_ref for node in nodes for output_ref in node.output_contract_refs}
    available_refs = set(external_refs) | produced_refs
    if configured_refs is not None:
        available_refs.update(configured_refs)
    return frozenset(available_refs)


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
