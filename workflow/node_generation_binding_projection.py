"""Output projection declaration checks for generation bindings."""

from __future__ import annotations

import re
from typing import Any, cast

from workflow.node_generation_binding_common import NodeGenerationBindingError

MAX_PROJECTION_POINTER_DEPTH = 64
TARGET_SLOT_PREFIX_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*\.$")
MAX_TARGET_SLOT_PREFIX_LENGTH = 159


def validate_projection_pointer(pointer: object, *, allow_root: bool = True) -> None:
    if not isinstance(pointer, str) or len(pointer) > 2048:
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROJECTION_POINTER_INVALID",
            "projection pointer must be a bounded string",
        )
    if pointer == "":
        if allow_root:
            return
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROJECTION_POINTER_INVALID",
            "projection pointer cannot be empty",
        )
    if not pointer.startswith("/") or "\\" in pointer or "#" in pointer:
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROJECTION_POINTER_INVALID",
            f"projection pointer is not RFC6901: {pointer}",
        )
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in pointer):
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROJECTION_POINTER_INVALID",
            "projection pointer contains a control character",
        )
    tokens = pointer.split("/")[1:]
    if len(tokens) > MAX_PROJECTION_POINTER_DEPTH:
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROJECTION_POINTER_INVALID",
            "projection pointer is too deep",
        )
    for token in tokens:
        _validate_projection_token(token, pointer)


def _validate_projection_token(token: str, pointer: str) -> None:
    if "*" in token or token in {"-", ".", ".."} or "[" in token or "]" in token:
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROJECTION_POINTER_INVALID",
            f"projection pointer uses an unsupported token: {pointer}",
        )
    index = 0
    while index < len(token):
        if token[index] != "~":
            index += 1
            continue
        if index + 1 >= len(token) or token[index + 1] not in {"0", "1"}:
            raise NodeGenerationBindingError(
                "NODE_BINDING_PROJECTION_POINTER_INVALID",
                f"projection pointer has an invalid escape: {pointer}",
            )
        index += 2


def validate_value_projection(value: dict[str, Any], *, item: bool = False) -> None:
    source = value.get("source")
    if source == "constant":
        return
    if source == "intrinsic":
        if value.get("name") != "item_position" or not item:
            raise NodeGenerationBindingError(
                "NODE_BINDING_PROJECTION_SOURCE_INVALID",
                "only item_position may be used for item mappings",
            )
        return
    if source not in {"output", "item", "runtime"}:
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROJECTION_SOURCE_INVALID",
            "projection source is not allowed",
        )
    if source == "item" and not item:
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROJECTION_SOURCE_INVALID",
            "item projection is only valid for package items",
        )
    pointer = cast(str, value.get("pointer"))
    validate_projection_pointer(pointer)
    if source == "runtime" and not _is_allowed_runtime_pointer(pointer):
        raise NodeGenerationBindingError(
            "NODE_BINDING_RUNTIME_POINTER_INVALID",
            "runtime projections may expose only trusted runtime values",
        )


def _is_allowed_runtime_pointer(pointer: str) -> bool:
    return pointer in {"/lesson_key", "/reference_assets"} or pointer.startswith("/relation_keys/")


def validate_projection_declarations(node: dict[str, Any]) -> None:
    output_persistence = node.get("output_persistence")
    if output_persistence is None:
        return
    output_refs = cast(list[str], node["output_contract_refs"])
    if len(output_refs) != 1:
        raise NodeGenerationBindingError(
            "NODE_BINDING_OUTPUT_CONTRACT_AMBIGUOUS",
            f"output persistence must map to exactly one output contract: {node['node_key']}",
        )
    persistence = cast(dict[str, Any], output_persistence)
    artifact = cast(dict[str, Any], persistence["artifact"])
    content = _validate_artifact_declaration(node, artifact)
    _validate_artifact_relations(node, artifact)
    _validate_creation_package(node, persistence, content)


def _validate_artifact_declaration(
    node: dict[str, Any], artifact: dict[str, Any]
) -> dict[str, Any]:
    scope = cast(str, node["execution_scope"])
    identity = cast(dict[str, Any], artifact["identity"])
    expected_strategy = "project_singleton" if scope == "project" else "lesson_unit_singleton"
    if identity["strategy"] != expected_strategy:
        raise NodeGenerationBindingError(
            "NODE_BINDING_ARTIFACT_IDENTITY_INVALID",
            f"artifact identity does not match scope: {node['node_key']}",
        )
    expected_branch = "project" if scope == "project" else node["branch_key"]
    if artifact["branch_key"] != expected_branch:
        raise NodeGenerationBindingError(
            "NODE_BINDING_ARTIFACT_BRANCH_INVALID",
            f"artifact branch does not match node scope: {node['node_key']}",
        )
    content = cast(dict[str, Any], artifact["content"])
    if content != {"source": "output", "pointer": ""}:
        raise NodeGenerationBindingError(
            "NODE_BINDING_ARTIFACT_CONTENT_INVALID",
            f"artifact content must preserve validated output: {node['node_key']}",
        )
    validate_value_projection(content)
    return content


def _validate_artifact_relations(node: dict[str, Any], artifact: dict[str, Any]) -> None:
    relation_keys: set[tuple[str, str]] = set()
    optional_inputs = set(cast(list[str], node.get("optional_input_contract_refs", [])))
    for relation in cast(list[dict[str, Any]], artifact["relations"]):
        source_binding = cast(str, relation["source_binding"])
        if source_binding not in node["input_contract_refs"]:
            raise NodeGenerationBindingError(
                "NODE_BINDING_RELATION_SOURCE_INVALID",
                f"relation source is not an input contract: {source_binding}",
            )
        if (relation.get("optional") is True) != (source_binding in optional_inputs):
            raise NodeGenerationBindingError(
                "NODE_BINDING_RELATION_OPTIONALITY_INVALID",
                f"relation optionality does not match its input: {source_binding}",
            )
        identity_key = (source_binding, cast(str, relation["binding_key"]))
        if identity_key in relation_keys:
            raise NodeGenerationBindingError(
                "NODE_BINDING_RELATION_DUPLICATE",
                f"duplicate relation binding: {identity_key[1]}",
            )
        relation_keys.add(identity_key)
        impact_scope = cast(dict[str, Any], relation["impact_scope"])
        if relation["relation_type"] == "supersedes" and (
            source_binding not in optional_inputs or impact_scope != {"mode": "all"}
        ):
            raise NodeGenerationBindingError(
                "NODE_BINDING_SUPERSEDES_DECLARATION_INVALID",
                "generated supersedes requires an optional exact source and all impact",
            )
        _validate_impact_scope(node, impact_scope)


def _validate_impact_scope(node: dict[str, Any], impact_scope: dict[str, Any]) -> None:
    if impact_scope["mode"] != "keyed":
        return
    if node["execution_scope"] != "lesson_unit":
        raise NodeGenerationBindingError(
            "NODE_BINDING_IMPACT_SCOPE_INVALID",
            "keyed impact scope requires a lesson-unit execution scope",
        )
    keys = cast(dict[str, Any], impact_scope["keys"])
    if keys.get("source") != "runtime" or keys.get("pointer") != "/lesson_key":
        raise NodeGenerationBindingError(
            "NODE_BINDING_IMPACT_SCOPE_INVALID",
            "keyed impact scope must read runtime lesson_key",
        )


def _validate_creation_package(
    node: dict[str, Any], persistence: dict[str, Any], content: dict[str, Any]
) -> None:
    package = persistence.get("creation_package")
    package_outputs = [
        ref for ref in node["output_contract_refs"] if cast(str, ref).startswith("package:")
    ]
    if package_outputs and package is None:
        raise NodeGenerationBindingError(
            "NODE_BINDING_CREATION_PACKAGE_REQUIRED",
            f"package output requires a creation package declaration: {node['node_key']}",
        )
    if package is not None and not package_outputs:
        raise NodeGenerationBindingError(
            "NODE_BINDING_CREATION_PACKAGE_FORBIDDEN",
            f"creation package declaration has no package output: {node['node_key']}",
        )
    if package is None:
        return
    _validate_creation_package_content(cast(dict[str, Any], package), content)


def _validate_creation_package_content(package: dict[str, Any], content: dict[str, Any]) -> None:
    if content != {"source": "output", "pointer": ""}:
        raise NodeGenerationBindingError(
            "NODE_BINDING_CREATION_PACKAGE_CONTENT_INVALID",
            "creation package nodes must persist the complete validated output",
        )
    validate_projection_pointer(cast(str, package["items_pointer"]))
    _validate_target_slot_prefix(cast(dict[str, Any], package["target_rules"]))
    item_mapping = cast(dict[str, dict[str, Any]], package["item_mapping"])
    for field_name, mapping in item_mapping.items():
        validate_value_projection(mapping, item=True)
        if field_name == "reference_assets":
            _validate_reference_assets_mapping(mapping)


def _validate_target_slot_prefix(target_rules: dict[str, Any]) -> None:
    target_slot_prefix = target_rules.get("target_slot_prefix")
    if (
        type(target_slot_prefix) is not str
        or len(target_slot_prefix) > MAX_TARGET_SLOT_PREFIX_LENGTH
        or TARGET_SLOT_PREFIX_PATTERN.fullmatch(target_slot_prefix) is None
    ):
        raise NodeGenerationBindingError(
            "NODE_BINDING_TARGET_SLOT_PREFIX_INVALID",
            "target-slot prefix must leave room for a semantic slot suffix",
        )


def _validate_reference_assets_mapping(mapping: dict[str, Any]) -> None:
    if mapping not in (
        {"source": "runtime", "pointer": "/reference_assets"},
        {"source": "constant", "value": []},
    ):
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_ASSETS_INVALID",
            "reference assets must use the trusted runtime set or an empty constant",
        )
