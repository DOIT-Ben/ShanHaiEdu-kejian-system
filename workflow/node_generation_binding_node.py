"""Per-node declaration checks for workflow generation bindings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from workflow.node_generation_binding_common import (
    NodeGenerationBindingError,
    validate_executor,
    validate_model_capability,
    validate_unique_strings,
    validate_validator_refs,
)
from workflow.node_generation_binding_projection import validate_projection_declarations

DETERMINISTIC_OUTPUT_EXECUTORS = frozenset(
    {"executor.ppt.pages_assemble", "executor.ppt.pptx_export"}
)


def validate_node(node: dict[str, Any]) -> None:
    validate_execution_kind_declaration(node)
    _validate_deterministic_output(node)
    _validate_prompt_exposure(node)
    validate_unique_strings(node, "input_contract_refs", "NODE_BINDING_CONTRACT_REF_DUPLICATE")
    if "optional_input_contract_refs" in node:
        validate_unique_strings(
            node,
            "optional_input_contract_refs",
            "NODE_BINDING_OPTIONAL_INPUT_INVALID",
        )
    _validate_optional_inputs(node)
    validate_unique_strings(node, "output_contract_refs", "NODE_BINDING_CONTRACT_REF_DUPLICATE")
    validate_validator_refs(node)
    _validate_instruction_policy(cast(dict[str, Any], node["instruction_policy"]))
    _validate_context_policy(cast(dict[str, Any], node["context_policy"]))
    _validate_reference_asset_policy(cast(dict[str, Any], node["reference_asset_policy"]))
    validate_projection_declarations(node)
    _validate_quality_source_binding(node)
    if node["execution_kind"] == "model_generation":
        validate_model_capability(cast(str, node["model_capability"]))
        if not node["validator_refs"]:
            raise NodeGenerationBindingError(
                "NODE_BINDING_VALIDATOR_REQUIRED",
                f"model node requires a validator: {node['node_key']}",
            )
    elif node["execution_kind"] == "deterministic":
        validate_executor(cast(str, node["executor_ref"]))
    elif not cast(dict[str, Any], node["approval_policy"])["required_before_downstream"]:
        raise NodeGenerationBindingError(
            "NODE_BINDING_HUMAN_GATE_INVALID",
            f"human gate must block downstream execution: {node['node_key']}",
        )


def _validate_optional_inputs(node: dict[str, Any]) -> None:
    optional = set(cast(list[str], node.get("optional_input_contract_refs", [])))
    inputs = set(cast(list[str], node["input_contract_refs"]))
    if not optional <= inputs:
        raise NodeGenerationBindingError(
            "NODE_BINDING_OPTIONAL_INPUT_INVALID",
            f"optional inputs must be declared inputs: {node['node_key']}",
        )


def validate_execution_kind_declaration(node: dict[str, Any]) -> None:
    kind = node.get("execution_kind")
    rules = {
        "model_generation": (
            {"model_capability", "generation_template_ref", "output_persistence"},
            {"executor_ref", "quality_report_persistence", "quality_requirement"},
        ),
        "deterministic": (
            {"executor_ref"},
            {
                "model_capability",
                "generation_template_ref",
                "quality_requirement",
            },
        ),
        "human_gate": (
            {"quality_requirement"},
            {
                "model_capability",
                "generation_template_ref",
                "executor_ref",
                "output_persistence",
                "quality_report_persistence",
            },
        ),
    }
    rule = rules.get(cast(str, kind))
    if rule is None:
        raise NodeGenerationBindingError(
            "NODE_BINDING_EXECUTION_KIND_INVALID",
            f"node has an unsupported execution kind: {node.get('node_key')}",
        )
    required, forbidden = rule
    missing = required - node.keys()
    incompatible = forbidden & node.keys()
    if missing or incompatible:
        raise NodeGenerationBindingError(
            "NODE_BINDING_EXECUTION_KIND_INVALID",
            f"node has incompatible execution fields: {node.get('node_key')}",
        )


def _validate_deterministic_output(node: dict[str, Any]) -> None:
    if node.get("execution_kind") != "deterministic":
        return
    supports_output = node.get("executor_ref") in DETERMINISTIC_OUTPUT_EXECUTORS
    declares_output = "output_persistence" in node
    if supports_output != declares_output:
        raise NodeGenerationBindingError(
            "NODE_BINDING_DETERMINISTIC_OUTPUT_INVALID",
            f"deterministic output persistence is not allowed for {node['node_key']}",
        )


def _validate_quality_source_binding(node: dict[str, Any]) -> None:
    persistence = node.get("output_persistence")
    if not isinstance(persistence, dict):
        return
    persistence_values = cast(Mapping[str, object], persistence)
    completion = persistence_values.get("approval_completion")
    source = persistence_values.get("quality_source_binding")
    if completion is None:
        if source is not None:
            raise NodeGenerationBindingError(
                "NODE_BINDING_QUALITY_SOURCE_BINDING_INVALID",
                f"ungated output cannot declare a quality source binding: {node['node_key']}",
            )
        return
    outputs = cast(list[str], node["output_contract_refs"])
    valid = source == "artifact" and any(ref.startswith("artifact:") for ref in outputs)
    valid = valid or (
        source == "linked_file_asset" and any(ref.startswith("asset:") for ref in outputs)
    )
    if not valid:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_SOURCE_BINDING_INVALID",
            f"quality source binding is missing or incompatible: {node['node_key']}",
        )


def _validate_prompt_exposure(node: dict[str, Any]) -> None:
    policy = cast(dict[str, Any], node["prompt_exposure_policy"])
    teacher_surface = policy["teacher_business_prompt"]
    if node["execution_kind"] == "model_generation" and teacher_surface == "not_applicable":
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROMPT_EXPOSURE_INVALID",
            f"model node must declare an editable or hidden business prompt: {node['node_key']}",
        )
    if node["execution_kind"] != "model_generation" and teacher_surface != "not_applicable":
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROMPT_EXPOSURE_INVALID",
            f"non-model node cannot expose a business prompt: {node['node_key']}",
        )


def _validate_instruction_policy(policy: dict[str, Any]) -> None:
    refs = cast(list[dict[str, Any]], policy["refs"])
    identities = [
        (ref["content_key"], ref["content_kind"], ref["semantic_version"]) for ref in refs
    ]
    if len(identities) != len(set(identities)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_INSTRUCTION_REF_DUPLICATE",
            "instruction policy contains duplicate immutable content references",
        )


def _validate_context_policy(policy: dict[str, Any]) -> None:
    allowed = cast(list[str], policy["allowed_sources"])
    forbidden = cast(list[str], policy["forbidden_sources"])
    if len(allowed) != len(set(allowed)) or len(forbidden) != len(set(forbidden)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_CONTEXT_SOURCE_DUPLICATE",
            "context policy contains duplicate source values",
        )
    overlap = set(allowed) & set(forbidden)
    if overlap:
        raise NodeGenerationBindingError(
            "NODE_BINDING_CONTEXT_CONFLICT",
            f"context sources cannot be both allowed and forbidden: {sorted(overlap)}",
        )


def _validate_reference_asset_policy(policy: dict[str, Any]) -> None:
    roles = cast(list[dict[str, Any]], policy["roles"])
    keys = [cast(str, role["role_key"]) for role in roles]
    if len(keys) != len(set(keys)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_ROLE_DUPLICATE",
            "reference asset policy contains duplicate role_key values",
        )
    for role in roles:
        _validate_reference_role(role)
    required_roles = [role for role in roles if role["requirement"] == "required"]
    if policy["mode"] == "required" and not required_roles:
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_POLICY_INVALID",
            "required reference asset policy needs at least one required role",
        )
    if policy["mode"] == "optional" and required_roles:
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_POLICY_INVALID",
            "optional reference asset policy cannot contain required roles",
        )


def _validate_reference_role(role: dict[str, Any]) -> None:
    minimum = cast(int, role["min_items"])
    maximum = cast(int, role["max_items"])
    if maximum < minimum:
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_CARDINALITY_INVALID",
            f"reference role max_items is below min_items: {role['role_key']}",
        )
    if role["requirement"] == "required" and minimum < 1:
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_CARDINALITY_INVALID",
            f"required reference role must have min_items >= 1: {role['role_key']}",
        )
    if role["requirement"] == "optional" and minimum != 0:
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_CARDINALITY_INVALID",
            f"optional reference role must have min_items = 0: {role['role_key']}",
        )
    for field in ("media_types", "allowed_sources", "provider_exposure"):
        values = cast(list[str], role[field])
        if len(values) != len(set(values)):
            raise NodeGenerationBindingError(
                "NODE_BINDING_REFERENCE_VALUE_DUPLICATE",
                f"reference role contains duplicate {field}: {role['role_key']}",
            )
