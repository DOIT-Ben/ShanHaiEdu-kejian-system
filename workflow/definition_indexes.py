"""Immutable runtime indexes derived from published workflow definitions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from workflow.definition import (
    WorkflowApprovalCompletionBinding,
    WorkflowDefinitionError,
    WorkflowGraph,
    WorkflowIndexes,
    WorkflowNodeDefinition,
    WorkflowOutputDefinitionBinding,
    WorkflowProducerRef,
    validate_workflow_graph,
)
from workflow.definition_quality import QualityBinding, resolve_quality_binding
from workflow.definition_values import (
    as_mapping,
    require_text,
    require_text_value,
)


def build_workflow_indexes(graph: WorkflowGraph) -> WorkflowIndexes:
    """Build indexes from the immutable binding snapshot without inference."""

    validate_workflow_graph(graph)
    producers, scoped = _build_producer_indexes(graph.nodes)
    output_entries = _build_output_definition_index(graph.nodes)
    return _freeze_indexes(producers, scoped, output_entries)


def _build_producer_indexes(
    nodes: tuple[WorkflowNodeDefinition, ...],
) -> tuple[
    dict[str, list[WorkflowProducerRef]],
    dict[tuple[str, str, str], WorkflowProducerRef],
]:
    producers: dict[str, list[WorkflowProducerRef]] = defaultdict(list)
    scoped: dict[tuple[str, str, str], WorkflowProducerRef] = {}
    for node in nodes:
        if not isinstance(node.branch_key, str):
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has no concrete branch key",
                code="WORKFLOW_NODE_BRANCH_INVALID",
            )
        producer = WorkflowProducerRef(
            node_key=node.node_key,
            execution_scope=node.execution_scope,
            branch_key=node.branch_key,
            output_contract_refs=tuple(node.output_contract_refs),
        )
        for contract_ref in node.output_contract_refs:
            scoped_key = (node.execution_scope, node.branch_key, contract_ref)
            if scoped_key in scoped:
                previous = scoped[scoped_key]
                raise WorkflowDefinitionError(
                    f"contract {contract_ref} has multiple producers in "
                    f"{node.execution_scope}/{node.branch_key}: "
                    f"{previous.node_key}, {node.node_key}",
                    code="WORKFLOW_OUTPUT_PRODUCER_DUPLICATE",
                )
            scoped[scoped_key] = producer
            producers[contract_ref].append(producer)
    return producers, scoped


def _build_output_definition_index(
    nodes: tuple[WorkflowNodeDefinition, ...],
) -> dict[str, WorkflowOutputDefinitionBinding]:
    output_entries: dict[str, WorkflowOutputDefinitionBinding] = {}
    identity_declarations: list[tuple[str, str, str]] = []
    for node in nodes:
        if node.execution_kind != "model_generation":
            continue
        binding, persistence, artifact = _read_output_persistence(node)
        _validate_artifact_identity(node, artifact, identity_declarations)
        _validate_package_declaration(node, persistence)
        content_key, generation_key = _read_output_definition_refs(node, binding, artifact)
        if content_key in output_entries:
            previous = output_entries[content_key]
            raise WorkflowDefinitionError(
                f"content definition {content_key} has multiple producers: "
                f"{previous.producer_node_key}, {node.node_key}",
                code="WORKFLOW_OUTPUT_DEFINITION_DUPLICATE",
            )
        quality = resolve_quality_binding(node, nodes)
        output_entries[content_key] = _output_binding(
            node,
            artifact,
            content_key,
            generation_key,
            quality,
        )
    return output_entries


def _read_output_persistence(
    node: WorkflowNodeDefinition,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    binding = as_mapping(node.binding)
    if binding is None:
        raise WorkflowDefinitionError(
            f"model node {node.node_key} has an invalid binding",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    persistence = as_mapping(binding.get("output_persistence"))
    if persistence is None:
        raise WorkflowDefinitionError(
            f"model node {node.node_key} has no output persistence",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    artifact = as_mapping(persistence.get("artifact"))
    if artifact is None:
        raise WorkflowDefinitionError(
            f"model node {node.node_key} has an invalid output persistence",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    return binding, persistence, artifact


def _validate_artifact_identity(
    node: WorkflowNodeDefinition,
    artifact: Mapping[str, Any],
    identity_declarations: list[tuple[str, str, str]],
) -> None:
    identity = as_mapping(artifact.get("identity"))
    if identity is None:
        raise WorkflowDefinitionError(
            f"model node {node.node_key} has no artifact identity",
            code="WORKFLOW_OUTPUT_IDENTITY_INVALID",
        )
    expected_strategy = (
        "project_singleton" if node.execution_scope == "project" else "lesson_unit_singleton"
    )
    strategy = require_text(identity, "strategy")
    if strategy != expected_strategy:
        raise WorkflowDefinitionError(
            f"model node {node.node_key} has an identity incompatible with its scope",
            code="WORKFLOW_OUTPUT_IDENTITY_INVALID",
        )
    field = "artifact_key" if strategy == "project_singleton" else "artifact_key_prefix"
    identity_value = require_text(identity, field)
    for previous_strategy, previous_value, previous_node in identity_declarations:
        if _artifact_identities_overlap(
            strategy,
            identity_value,
            previous_strategy,
            previous_value,
        ):
            raise WorkflowDefinitionError(
                f"artifact identity for {node.node_key} overlaps {previous_node}",
                code="WORKFLOW_OUTPUT_IDENTITY_DUPLICATE",
            )
    identity_declarations.append((strategy, identity_value, node.node_key))
    expected_branch = "project" if node.execution_scope == "project" else node.branch_key
    if artifact.get("branch_key") != expected_branch:
        raise WorkflowDefinitionError(
            f"model node {node.node_key} has an invalid artifact branch",
            code="WORKFLOW_OUTPUT_ARTIFACT_BRANCH_INVALID",
        )


def _validate_package_declaration(
    node: WorkflowNodeDefinition,
    persistence: Mapping[str, Any],
) -> None:
    package = as_mapping(persistence.get("creation_package"))
    package_outputs = tuple(ref for ref in node.output_contract_refs if ref.startswith("package:"))
    if (package is None) != (not package_outputs) or len(package_outputs) > 1:
        raise WorkflowDefinitionError(
            f"model node {node.node_key} has an inconsistent package declaration",
            code="WORKFLOW_OUTPUT_PACKAGE_INVALID",
        )


def _read_output_definition_refs(
    node: WorkflowNodeDefinition,
    binding: Mapping[str, Any],
    artifact: Mapping[str, Any],
) -> tuple[str, str]:
    content_ref = as_mapping(artifact.get("content_definition_ref"))
    generation_ref = as_mapping(binding.get("generation_template_ref"))
    if content_ref is None:
        raise WorkflowDefinitionError(
            f"model node {node.node_key} has an invalid content definition ref",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    if len(node.output_contract_refs) != 1:
        raise WorkflowDefinitionError(
            f"model node {node.node_key} must map output persistence to exactly one contract",
            code="WORKFLOW_OUTPUT_CONTRACT_AMBIGUOUS",
        )
    if generation_ref is None or generation_ref.get("kind") != "generation_template":
        raise WorkflowDefinitionError(
            f"model node {node.node_key} has an invalid generation template ref",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    content_key = require_text(content_ref, "item_key")
    generation_key = require_text(generation_ref, "item_key")
    if content_ref.get("kind") != "content_definition":
        raise WorkflowDefinitionError(
            f"output definition kind is invalid for {node.node_key}",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    return content_key, generation_key


def _output_binding(
    node: WorkflowNodeDefinition,
    artifact: Mapping[str, Any],
    content_key: str,
    generation_key: str,
    quality: QualityBinding,
) -> WorkflowOutputDefinitionBinding:
    completion = _approval_completion(node)
    return WorkflowOutputDefinitionBinding(
        content_definition_key=content_key,
        generation_template_key=generation_key,
        producer_node_key=node.node_key,
        execution_scope=node.execution_scope,
        producer_branch_key=require_text_value(node.branch_key, "branch_key"),
        artifact_branch_key=require_text(artifact, "branch_key"),
        artifact_type=require_text(artifact, "artifact_type"),
        output_contract_refs=tuple(node.output_contract_refs),
        quality_validate_node_key=quality[0],
        quality_report_refs=quality[1],
        quality_validator_refs=quality[2],
        quality_gate_node_key=quality[3],
        quality_requirement_mode=quality[4],
        approval_completion=completion,
    )


def _approval_completion(
    node: WorkflowNodeDefinition,
) -> WorkflowApprovalCompletionBinding | None:
    binding = as_mapping(node.binding)
    persistence = as_mapping(binding.get("output_persistence")) if binding is not None else None
    completion = (
        as_mapping(persistence.get("approval_completion")) if persistence is not None else None
    )
    if completion is None:
        return None
    return WorkflowApprovalCompletionBinding(
        kind=require_text(completion, "kind"),
        collection_pointer=require_text(completion, "collection_pointer"),
        stable_key_field=require_text(completion, "stable_key_field"),
    )


def _freeze_indexes(
    producers: dict[str, list[WorkflowProducerRef]],
    scoped: dict[tuple[str, str, str], WorkflowProducerRef],
    output_entries: dict[str, WorkflowOutputDefinitionBinding],
) -> WorkflowIndexes:
    producer_values = {
        key: tuple(
            sorted(
                values,
                key=lambda item: (item.execution_scope, item.branch_key, item.node_key),
            )
        )
        for key, values in producers.items()
    }
    scoped_values = {
        key: scoped[key] for key in sorted(scoped, key=lambda item: (item[0], item[1], item[2]))
    }
    output_values = {key: output_entries[key] for key in sorted(output_entries)}
    return WorkflowIndexes(
        producers_by_contract=MappingProxyType(producer_values),
        producer_index=MappingProxyType(scoped_values),
        output_definition_index=MappingProxyType(output_values),
    )


def _artifact_identities_overlap(
    strategy: str,
    value: str,
    other_strategy: str,
    other_value: str,
) -> bool:
    if strategy == other_strategy == "project_singleton":
        return value == other_value
    if strategy == other_strategy == "lesson_unit_singleton":
        return (
            value == other_value
            or value.startswith(f"{other_value}:")
            or other_value.startswith(f"{value}:")
        )
    project_key, lesson_prefix = (
        (value, other_value) if strategy == "project_singleton" else (other_value, value)
    )
    return project_key.startswith(f"{lesson_prefix}:")
