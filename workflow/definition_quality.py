"""Quality validator and human-gate resolution for workflow outputs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from workflow.definition import WorkflowDefinitionError, WorkflowNodeDefinition
from workflow.definition_values import (
    as_mapping,
    descriptor_identity,
    require_sequence,
    require_text,
    require_text_value,
)

QualityBinding = tuple[
    str | None,
    tuple[str, ...],
    tuple[tuple[str, str, str], ...],
    str | None,
    str,
]


def resolve_quality_binding(
    producer: WorkflowNodeDefinition,
    nodes: tuple[WorkflowNodeDefinition, ...],
) -> QualityBinding:
    candidates = _quality_candidates(producer, nodes)
    if len(candidates) > 1:
        raise WorkflowDefinitionError(
            f"content definition producer {producer.node_key} has ambiguous quality validators",
            code="WORKFLOW_OUTPUT_QUALITY_AMBIGUOUS",
        )
    gates = _quality_gates(producer, nodes)
    if candidates:
        validate_node, quality = candidates[0]
        return _resolve_report_quality_binding(producer, validate_node, quality, gates)
    return _resolve_direct_quality_binding(producer, gates)


def _quality_candidates(
    producer: WorkflowNodeDefinition,
    nodes: tuple[WorkflowNodeDefinition, ...],
) -> list[tuple[WorkflowNodeDefinition, Mapping[str, Any]]]:
    candidates: list[tuple[WorkflowNodeDefinition, Mapping[str, Any]]] = []
    for node in nodes:
        if (
            node.execution_kind != "deterministic"
            or node.execution_scope != producer.execution_scope
            or node.branch_key != producer.branch_key
            or producer.node_key not in node.dependencies
        ):
            continue
        node_binding = as_mapping(node.binding)
        quality = as_mapping(
            node_binding.get("quality_report_persistence") if node_binding is not None else None
        )
        if quality is None:
            continue
        if quality.get("source_input_ref") in producer.output_contract_refs:
            candidates.append((node, quality))
    return candidates


def _quality_gates(
    producer: WorkflowNodeDefinition,
    nodes: tuple[WorkflowNodeDefinition, ...],
) -> list[WorkflowNodeDefinition]:
    return [
        node
        for node in nodes
        if (
            node.execution_kind == "human_gate"
            and node.execution_scope == producer.execution_scope
            and node.branch_key == producer.branch_key
        )
    ]


def _resolve_report_quality_binding(
    producer: WorkflowNodeDefinition,
    validate_node: WorkflowNodeDefinition,
    quality: Mapping[str, Any],
    gates: list[WorkflowNodeDefinition],
) -> QualityBinding:
    source_ref, report_refs, validator_refs = _validate_report_declaration(validate_node, quality)
    report_ref = report_refs[0]
    matching = _matching_report_gates(
        producer,
        validate_node,
        source_ref,
        report_ref,
        gates,
    )
    if not matching:
        raise WorkflowDefinitionError(
            f"quality report {report_ref} has no human gate for {producer.node_key}",
            code="WORKFLOW_OUTPUT_QUALITY_GATE_MISSING",
        )
    if len(matching) > 1:
        raise WorkflowDefinitionError(
            f"content definition producer {producer.node_key} has ambiguous quality gates",
            code="WORKFLOW_OUTPUT_QUALITY_AMBIGUOUS",
        )
    gate, gate_reports = matching[0]
    _validate_gate_report_set(gate, gate_reports, report_refs)
    return (
        validate_node.node_key,
        report_refs,
        validator_refs,
        gate.node_key,
        "reports",
    )


def _validate_report_declaration(
    validate_node: WorkflowNodeDefinition,
    quality: Mapping[str, Any],
) -> tuple[str, tuple[str, ...], tuple[tuple[str, str, str], ...]]:
    source_ref = require_text(quality, "source_input_ref")
    report_ref = require_text(quality, "report_ref")
    if (
        source_ref not in validate_node.input_contract_refs
        or report_ref not in validate_node.output_contract_refs
    ):
        raise WorkflowDefinitionError(
            f"quality validator {validate_node.node_key} has inconsistent contracts",
            code="WORKFLOW_OUTPUT_QUALITY_INVALID",
        )
    validator_refs = tuple(
        descriptor_identity(ref)
        for ref in require_sequence(quality.get("validator_refs"), "validator_refs")
    )
    if not validator_refs:
        raise WorkflowDefinitionError(
            f"quality validator {validate_node.node_key} has no validator descriptors",
            code="WORKFLOW_OUTPUT_QUALITY_INVALID",
        )
    return source_ref, (report_ref,), validator_refs


def _matching_report_gates(
    producer: WorkflowNodeDefinition,
    validate_node: WorkflowNodeDefinition,
    source_ref: str,
    report_ref: str,
    gates: list[WorkflowNodeDefinition],
) -> list[tuple[WorkflowNodeDefinition, tuple[str, ...]]]:
    matching: list[tuple[WorkflowNodeDefinition, tuple[str, ...]]] = []
    for gate in gates:
        gate_binding = as_mapping(gate.binding)
        requirement = as_mapping(
            gate_binding.get("quality_requirement") if gate_binding is not None else None
        )
        if requirement is None or requirement.get("mode") != "reports":
            continue
        gate_reports = tuple(
            require_text_value(item, "report_ref")
            for item in require_sequence(requirement.get("report_refs"), "report_refs")
        )
        if report_ref not in gate_reports:
            continue
        if (
            producer.node_key not in gate.dependencies
            or validate_node.node_key not in gate.dependencies
            or source_ref not in gate.input_contract_refs
            or report_ref not in gate.input_contract_refs
        ):
            raise WorkflowDefinitionError(
                f"quality gate {gate.node_key} bypasses the declared validation chain",
                code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
            )
        matching.append((gate, gate_reports))
    return matching


def _validate_gate_report_set(
    gate: WorkflowNodeDefinition,
    gate_reports: tuple[str, ...],
    report_refs: tuple[str, ...],
) -> None:
    if len(gate_reports) != len(set(gate_reports)):
        raise WorkflowDefinitionError(
            f"quality gate {gate.node_key} contains duplicate report refs",
            code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
        )
    if set(gate_reports) != set(report_refs):
        raise WorkflowDefinitionError(
            f"quality gate {gate.node_key} has a different report set",
            code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
        )


def _resolve_direct_quality_binding(
    producer: WorkflowNodeDefinition,
    gates: list[WorkflowNodeDefinition],
) -> QualityBinding:
    direct_gates = [gate for gate in gates if producer.node_key in gate.dependencies]
    if len(direct_gates) > 1:
        raise WorkflowDefinitionError(
            f"content definition producer {producer.node_key} has ambiguous quality gates",
            code="WORKFLOW_OUTPUT_QUALITY_AMBIGUOUS",
        )
    gate = direct_gates[0] if direct_gates else None
    if gate is None:
        return (None, (), (), None, "none")
    gate_binding = as_mapping(gate.binding)
    requirement = as_mapping(
        gate_binding.get("quality_requirement") if gate_binding is not None else None
    )
    if requirement is None:
        raise WorkflowDefinitionError(
            f"quality gate {gate.node_key} has no quality requirement",
            code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
        )
    mode = require_text(requirement, "mode")
    if mode == "reports":
        raise WorkflowDefinitionError(
            f"quality gate {gate.node_key} has no deterministic report producer",
            code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
        )
    if not set(producer.output_contract_refs) <= set(gate.input_contract_refs):
        raise WorkflowDefinitionError(
            f"quality gate {gate.node_key} does not consume the producer output",
            code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
        )
    return (None, (), (), gate.node_key, mode)
