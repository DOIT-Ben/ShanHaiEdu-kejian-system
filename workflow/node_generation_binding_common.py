"""Shared validation primitives for workflow node generation bindings."""

from __future__ import annotations

import re
from typing import Any, cast

from workflow.model_capabilities import WORKFLOW_MODEL_CAPABILITIES

REGISTERED_MODEL_CAPABILITIES = WORKFLOW_MODEL_CAPABILITIES
FORBIDDEN_EXECUTOR_TOKENS = frozenset(
    {"bash", "cmd", "http", "https", "javascript", "node", "powershell", "python", "shell"}
)
TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


class NodeGenerationBindingError(ValueError):
    """Raised when a node binding catalog is unsafe or internally inconsistent."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def descriptor_identity(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        cast(str, value["key"]),
        cast(str, value["semantic_version"]),
        cast(str, value["implementation_digest"]),
    )


def require_unique_node_keys(nodes: list[dict[str, Any]]) -> None:
    keys = [cast(str, node["node_key"]) for node in nodes]
    if len(keys) != len(set(keys)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_DUPLICATE_NODE_KEY",
            "node binding catalog contains duplicate node_key values",
        )


def validate_validator_descriptors(catalog: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    raw_descriptors = cast(list[dict[str, Any]], catalog["validator_descriptors"])
    identities = [descriptor_identity(item) for item in raw_descriptors]
    if len(identities) != len(set(identities)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_VALIDATOR_DESCRIPTOR_DUPLICATE",
            "validator descriptors must have unique identities",
        )
    key_versions: dict[tuple[str, str], str] = {}
    for descriptor in raw_descriptors:
        key_version = (
            cast(str, descriptor["key"]),
            cast(str, descriptor["semantic_version"]),
        )
        digest = cast(str, descriptor["implementation_digest"])
        previous = key_versions.get(key_version)
        if previous is not None and previous != digest:
            raise NodeGenerationBindingError(
                "NODE_BINDING_VALIDATOR_DESCRIPTOR_CONFLICT",
                f"validator descriptor has conflicting digests: {key_version[0]}",
            )
        key_versions[key_version] = digest
        if digest == "0" * 64:
            raise NodeGenerationBindingError(
                "NODE_BINDING_VALIDATOR_DIGEST_INVALID",
                f"validator descriptor digest is not bound: {key_version[0]}",
            )

    descriptor_set = set(identities)
    for node in nodes:
        for ref in cast(list[dict[str, Any]], node["validator_refs"]):
            if descriptor_identity(ref) not in descriptor_set:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_VALIDATOR_DESCRIPTOR_UNRESOLVED",
                    f"validator reference is not declared: {ref['key']}",
                )


def validate_validator_refs(node: dict[str, Any]) -> None:
    refs = cast(list[dict[str, Any]], node["validator_refs"])
    identities = [descriptor_identity(ref) for ref in refs]
    if len(identities) != len(set(identities)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_VALIDATOR_REF_DUPLICATE",
            f"node contains duplicate validator_refs: {node['node_key']}",
        )


def validate_model_capability(capability: str) -> None:
    """Require a registered logical capability at the workflow contract boundary."""

    if capability not in REGISTERED_MODEL_CAPABILITIES:
        raise NodeGenerationBindingError(
            "NODE_BINDING_CAPABILITY_FORBIDDEN",
            f"model capability must be registered and provider-neutral: {capability}",
        )


def validate_executor(executor_ref: str) -> None:
    tokens = set(TOKEN_SPLIT.split(executor_ref.lower()))
    if tokens & FORBIDDEN_EXECUTOR_TOKENS:
        raise NodeGenerationBindingError(
            "NODE_BINDING_EXECUTOR_FORBIDDEN",
            f"executor_ref must identify a registered safe executor: {executor_ref}",
        )


def validate_unique_strings(node: dict[str, Any], field: str, code: str) -> None:
    values = cast(list[str], node[field])
    if len(values) != len(set(values)):
        raise NodeGenerationBindingError(
            code,
            f"node contains duplicate {field}: {node['node_key']}",
        )
