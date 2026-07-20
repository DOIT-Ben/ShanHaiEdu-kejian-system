"""Quality report and gate checks for workflow node generation bindings."""

from __future__ import annotations

from typing import Any, cast

from workflow.node_generation_binding_common import (
    NodeGenerationBindingError,
    descriptor_identity,
)
from workflow.node_generation_binding_projection import validate_value_projection

ReportKey = tuple[str, str, str]
ContractProducers = dict[ReportKey, list[dict[str, Any]]]
ReportProducers = dict[ReportKey, dict[str, Any]]


def validate_quality_contracts(nodes: list[dict[str, Any]]) -> None:
    contract_producers = _index_contract_producers(nodes)
    report_producers: ReportProducers = {}
    for node in nodes:
        persistence = node.get("quality_report_persistence")
        if persistence is not None:
            _register_quality_report(
                node,
                cast(dict[str, Any], persistence),
                contract_producers,
                report_producers,
            )

    consumed_reports: set[ReportKey] = set()
    for node in nodes:
        if node["execution_kind"] == "human_gate":
            _validate_quality_gate(node, contract_producers, report_producers, consumed_reports)
    orphaned = set(report_producers) - consumed_reports
    if orphaned:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_REPORT_ORPHANED",
            f"quality reports have no gate: {sorted(key[2] for key in orphaned)}",
        )


def _index_contract_producers(nodes: list[dict[str, Any]]) -> ContractProducers:
    contract_producers: ContractProducers = {}
    for node in nodes:
        scope_branch = (
            cast(str, node["execution_scope"]),
            cast(str, node["branch_key"]),
        )
        for output_ref in cast(list[str], node["output_contract_refs"]):
            contract_producers.setdefault((*scope_branch, output_ref), []).append(node)
    return contract_producers


def _register_quality_report(
    node: dict[str, Any],
    persistence: dict[str, Any],
    contract_producers: ContractProducers,
    report_producers: ReportProducers,
) -> None:
    report_ref, source = _validate_report_declaration(node, persistence)
    _validate_report_validators(node, persistence)
    _validate_report_mapping(node, persistence)
    scope_branch = (cast(str, node["execution_scope"]), cast(str, node["branch_key"]))
    _validate_report_dependencies(node, source, scope_branch, contract_producers)
    report_key = (*scope_branch, report_ref)
    if report_key in report_producers:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_REPORT_DUPLICATE",
            f"report has multiple producers: {report_ref}",
        )
    report_producers[report_key] = node


def _validate_report_declaration(
    node: dict[str, Any], persistence: dict[str, Any]
) -> tuple[str, str]:
    reports = [
        ref for ref in cast(list[str], node["output_contract_refs"]) if ref.startswith("report:")
    ]
    report_ref = cast(str, persistence["report_ref"])
    if report_ref not in reports:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_REPORT_INVALID",
            f"quality report is not an output of {node['node_key']}",
        )
    source = cast(str, persistence["source_input_ref"])
    if source not in node["input_contract_refs"]:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_SOURCE_INVALID",
            f"quality source is not an input of {node['node_key']}",
        )
    return report_ref, source


def _validate_report_validators(node: dict[str, Any], persistence: dict[str, Any]) -> None:
    validators = {
        descriptor_identity(ref)
        for ref in cast(list[dict[str, Any]], persistence["validator_refs"])
    }
    node_validators = {
        descriptor_identity(ref) for ref in cast(list[dict[str, Any]], node["validator_refs"])
    }
    if not validators or not validators <= node_validators:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_VALIDATOR_INVALID",
            f"quality report validators are not declared by {node['node_key']}",
        )
    if validators != node_validators:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_VALIDATOR_INVALID",
            f"quality report validators do not match {node['node_key']}",
        )


def _validate_report_mapping(node: dict[str, Any], persistence: dict[str, Any]) -> None:
    for value in cast(dict[str, dict[str, Any]], persistence["mapping"]).values():
        if value.get("source") != "output":
            raise NodeGenerationBindingError(
                "NODE_BINDING_QUALITY_MAPPING_INVALID",
                f"quality report mappings must use validator output: {node['node_key']}",
            )
        validate_value_projection(value)


def _validate_report_dependencies(
    node: dict[str, Any],
    source: str,
    scope_branch: tuple[str, str],
    contract_producers: ContractProducers,
) -> None:
    source_producers = contract_producers.get((*scope_branch, source), [])
    if (
        len(source_producers) != 1
        or cast(str, source_producers[0]["node_key"]) not in node["dependencies"]
    ):
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_SOURCE_INVALID",
            f"quality report bypasses its source producer: {node['node_key']}",
        )
    for input_ref in cast(list[str], node["input_contract_refs"]):
        if not input_ref.startswith("report:"):
            continue
        input_producers = contract_producers.get((*scope_branch, input_ref), [])
        if (
            len(input_producers) != 1
            or cast(str, input_producers[0]["node_key"]) not in node["dependencies"]
        ):
            raise NodeGenerationBindingError(
                "NODE_BINDING_QUALITY_REPORT_INPUT_INVALID",
                f"quality report bypasses an input report: {node['node_key']}",
            )


def _validate_quality_gate(
    node: dict[str, Any],
    contract_producers: ContractProducers,
    report_producers: ReportProducers,
    consumed_reports: set[ReportKey],
) -> None:
    requirement = cast(dict[str, Any], node["quality_requirement"])
    if requirement["mode"] != "reports":
        return
    report_refs = cast(list[str], requirement["report_refs"])
    if len(report_refs) != len(set(report_refs)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_GATE_INVALID",
            f"quality gate contains duplicate report refs: {node['node_key']}",
        )
    for report_ref in report_refs:
        _validate_gate_report(
            node,
            report_ref,
            contract_producers,
            report_producers,
            consumed_reports,
        )


def _validate_gate_report(
    node: dict[str, Any],
    report_ref: str,
    contract_producers: ContractProducers,
    report_producers: ReportProducers,
    consumed_reports: set[ReportKey],
) -> None:
    report_key = (
        cast(str, node["execution_scope"]),
        cast(str, node["branch_key"]),
        report_ref,
    )
    if report_ref not in node["input_contract_refs"]:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_GATE_INVALID",
            f"quality gate does not consume report: {node['node_key']}",
        )
    producer = report_producers.get(report_key)
    if producer is None:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_REPORT_UNRESOLVED",
            f"quality gate references an undeclared report: {report_ref}",
        )
    if cast(str, producer["node_key"]) not in node["dependencies"]:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_GATE_INVALID",
            f"quality gate bypasses report producer: {node['node_key']}",
        )
    _validate_gate_source(node, producer, contract_producers)
    if report_key in consumed_reports:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_GATE_INVALID",
            f"quality report has multiple gates: {report_ref}",
        )
    consumed_reports.add(report_key)


def _validate_gate_source(
    node: dict[str, Any], producer: dict[str, Any], contract_producers: ContractProducers
) -> None:
    persistence = cast(dict[str, Any], producer["quality_report_persistence"])
    source_ref = cast(str, persistence["source_input_ref"])
    source_producers = contract_producers.get(
        (
            cast(str, node["execution_scope"]),
            cast(str, node["branch_key"]),
            source_ref,
        ),
        [],
    )
    if (
        len(source_producers) != 1
        or cast(str, source_producers[0]["node_key"]) not in node["dependencies"]
        or source_ref not in node["input_contract_refs"]
    ):
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_GATE_INVALID",
            f"quality gate bypasses source producer: {node['node_key']}",
        )
