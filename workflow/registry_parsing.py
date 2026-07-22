"""Parsing and immutable snapshot helpers for workflow registry declarations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any, cast

from workflow.definition import (
    WorkflowDefinitionError,
    WorkflowNodeDefinition,
    freeze_workflow_value,
)

ValidatorDescriptorIndex = Mapping[tuple[str, str], Mapping[str, Any]]

_REQUIRED_NODE_FIELDS = (
    "node_key",
    "execution_kind",
    "execution_scope",
    "branch_key",
    "entrypoint",
    "dependencies",
    "input_contract_refs",
    "output_contract_refs",
)


def parse_string_array(
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


def parse_node(raw: object) -> WorkflowNodeDefinition:
    values = _parse_node_mapping(raw)
    _require_node_fields(values)
    node_key, execution_kind, execution_scope = _parse_required_node_strings(values)
    branch_key = _parse_branch_key(values)
    entrypoint = _parse_entrypoint(values)
    return WorkflowNodeDefinition(
        node_key=node_key,
        execution_kind=execution_kind,
        execution_scope=execution_scope,
        branch_key=branch_key,
        entrypoint=entrypoint,
        dependencies=parse_string_array(values, "dependencies", required=True),
        input_contract_refs=parse_string_array(
            values,
            "input_contract_refs",
            required=True,
        ),
        optional_input_contract_refs=parse_string_array(
            values,
            "optional_input_contract_refs",
        ),
        output_contract_refs=parse_string_array(
            values,
            "output_contract_refs",
            required=True,
        ),
        binding=cast(Mapping[str, Any], freeze_workflow_value(values)),
    )


def _parse_node_mapping(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise WorkflowDefinitionError(
            "workflow nodes must be objects",
            code="WORKFLOW_NODE_DECLARATION_INVALID",
        )
    return cast(dict[str, object], raw)


def _require_node_fields(values: Mapping[str, object]) -> None:
    missing = [name for name in _REQUIRED_NODE_FIELDS if name not in values]
    if missing:
        raise WorkflowDefinitionError(
            f"workflow node declaration is missing fields: {sorted(missing)}",
            code="WORKFLOW_NODE_DECLARATION_INVALID",
        )


def _parse_required_node_strings(values: Mapping[str, object]) -> tuple[str, str, str]:
    parsed: list[str] = []
    for field, label in (
        ("node_key", "node_key"),
        ("execution_scope", "execution_scope"),
        ("execution_kind", "execution_kind"),
    ):
        value = values[field]
        if not isinstance(value, str):
            raise WorkflowDefinitionError(
                f"workflow {label} must be a string",
                code="WORKFLOW_NODE_DECLARATION_INVALID",
            )
        parsed.append(value)
    return parsed[0], parsed[2], parsed[1]


def _parse_branch_key(values: Mapping[str, object]) -> str | None:
    branch_key = values["branch_key"]
    if branch_key is not None and not isinstance(branch_key, str):
        raise WorkflowDefinitionError(
            "workflow branch_key must be a string or null",
            code="WORKFLOW_NODE_DECLARATION_INVALID",
        )
    return branch_key


def _parse_entrypoint(values: Mapping[str, object]) -> bool:
    entrypoint = values["entrypoint"]
    if type(entrypoint) is not bool:
        raise WorkflowDefinitionError(
            "workflow entrypoint must be a boolean",
            code="WORKFLOW_NODE_DECLARATION_INVALID",
        )
    return entrypoint


def parse_validator_descriptors(payload: Mapping[str, object]) -> ValidatorDescriptorIndex:
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
        identity, descriptor = _parse_validator_descriptor(raw)
        _insert_validator_descriptor(descriptors, identity, descriptor)
    return MappingProxyType(descriptors)


def _parse_validator_descriptor(
    raw: object,
) -> tuple[tuple[str, str], Mapping[str, Any]]:
    if not isinstance(raw, dict):
        raise WorkflowDefinitionError(
            "workflow validator descriptors must be objects",
            code="WORKFLOW_VALIDATOR_DESCRIPTOR_INVALID",
        )
    descriptor = cast(dict[str, object], raw)
    key = descriptor.get("key")
    version = descriptor.get("semantic_version")
    digest = descriptor.get("implementation_digest")
    if not _valid_descriptor_fields(key, version, digest, descriptor.get("implementation_status")):
        raise WorkflowDefinitionError(
            "workflow validator descriptor is invalid",
            code="WORKFLOW_VALIDATOR_DESCRIPTOR_INVALID",
        )
    frozen = freeze_workflow_value(descriptor)
    assert isinstance(frozen, Mapping)
    return (cast(str, key), cast(str, version)), cast(Mapping[str, Any], frozen)


def _valid_descriptor_fields(
    key: object,
    version: object,
    digest: object,
    status: object,
) -> bool:
    return (
        type(key) is str
        and bool(key.strip())
        and type(version) is str
        and bool(version.strip())
        and type(digest) is str
        and len(digest) == 64
        and all(char in "0123456789abcdef" for char in digest)
        and digest != "0" * 64
        and status == "contract_only"
    )


def _insert_validator_descriptor(
    descriptors: dict[tuple[str, str], Mapping[str, Any]],
    identity: tuple[str, str],
    descriptor: Mapping[str, Any],
) -> None:
    prior = descriptors.get(identity)
    if prior is not None:
        key = identity[0]
        if prior["implementation_digest"] != descriptor["implementation_digest"]:
            raise WorkflowDefinitionError(
                f"workflow validator descriptor conflicts: {key}",
                code="WORKFLOW_VALIDATOR_DESCRIPTOR_CONFLICT",
            )
        raise WorkflowDefinitionError(
            f"workflow validator descriptor is duplicated: {key}",
            code="WORKFLOW_VALIDATOR_DESCRIPTOR_DUPLICATE",
        )
    descriptors[identity] = descriptor


def validate_node_validator_refs(
    nodes: tuple[WorkflowNodeDefinition, ...],
    descriptors: ValidatorDescriptorIndex,
) -> None:
    for node in nodes:
        for ref in _collect_node_validator_refs(node):
            _validate_validator_ref(node.node_key, ref, descriptors)


def _collect_node_validator_refs(node: WorkflowNodeDefinition) -> list[object]:
    refs = node.binding.get("validator_refs")
    if not isinstance(refs, (list, tuple)):
        raise WorkflowDefinitionError(
            f"workflow node {node.node_key} has invalid validator refs",
            code="WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED",
        )
    all_refs = list(cast(Sequence[object], refs))
    report = node.binding.get("quality_report_persistence")
    if isinstance(report, Mapping):
        report_values = cast(Mapping[str, object], report)
        report_refs = report_values.get("validator_refs")
        if not isinstance(report_refs, (list, tuple)):
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has invalid validator refs",
                code="WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED",
            )
        all_refs.extend(cast(Sequence[object], report_refs))
    return all_refs


def _validate_validator_ref(
    node_key: str,
    ref: object,
    descriptors: ValidatorDescriptorIndex,
) -> None:
    if not isinstance(ref, Mapping):
        raise WorkflowDefinitionError(
            f"workflow node {node_key} has invalid validator ref",
            code="WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED",
        )
    values = cast(Mapping[str, object], ref)
    key = values.get("key")
    version = values.get("semantic_version")
    digest = values.get("implementation_digest")
    if type(key) is not str or type(version) is not str or type(digest) is not str:
        raise WorkflowDefinitionError(
            f"workflow node {node_key} has unresolved validator ref",
            code="WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED",
        )
    descriptor = descriptors.get((key, version))
    if descriptor is None or descriptor["implementation_digest"] != digest:
        raise WorkflowDefinitionError(
            f"workflow node {node_key} has unresolved validator ref",
            code="WORKFLOW_VALIDATOR_DESCRIPTOR_UNRESOLVED",
        )
