"""Validation for declarative workflow node generation binding catalogs."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from workflow.definition import (
    WorkflowDefinitionError,
    WorkflowGraph,
    WorkflowIndexes,
    WorkflowNodeDefinition,
    build_workflow_indexes,
)
from workflow.model_capabilities import WORKFLOW_MODEL_CAPABILITIES

MAX_NODE_CATALOG_BYTES = 5_000_000
MAX_PROJECTION_POINTER_DEPTH = 64
REGISTERED_MODEL_CAPABILITIES = WORKFLOW_MODEL_CAPABILITIES
FORBIDDEN_EXECUTOR_TOKENS = frozenset(
    {"bash", "cmd", "http", "https", "javascript", "node", "powershell", "python", "shell"}
)
TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")
TARGET_SLOT_PREFIX_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*\.$")
MAX_TARGET_SLOT_PREFIX_LENGTH = 159


class NodeGenerationBindingError(ValueError):
    """Raised when a node binding catalog is unsafe or internally inconsistent."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ValidatedWorkflowNodeCatalog:
    catalog: dict[str, Any]
    canonical_json: bytes
    content_hash: str
    indexes: WorkflowIndexes


def canonical_catalog_json(catalog: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            catalog,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NodeGenerationBindingError(
            "NODE_BINDING_VALUE_INVALID",
            "node binding catalog must contain finite JSON values",
        ) from exc


def load_workflow_node_catalog(
    catalog_path: Path,
    *,
    schema_path: Path,
) -> ValidatedWorkflowNodeCatalog:
    catalog = _load_object(catalog_path)
    schema = _load_object(schema_path)
    return validate_workflow_node_catalog(catalog, schema=schema)


def validate_workflow_node_catalog(
    catalog: dict[str, Any],
    *,
    schema: dict[str, Any],
) -> ValidatedWorkflowNodeCatalog:
    _validate_schema(catalog, schema)
    indexes = validate_workflow_node_catalog_semantics(catalog)
    canonical = canonical_catalog_json(catalog)
    return ValidatedWorkflowNodeCatalog(
        catalog=catalog,
        canonical_json=canonical,
        content_hash=hashlib.sha256(canonical).hexdigest(),
        indexes=indexes,
    )


def validate_workflow_node_catalog_semantics(catalog: dict[str, Any]) -> WorkflowIndexes:
    """Validate a schema-conformant catalog with the shared runtime semantics."""

    nodes = cast(list[dict[str, Any]], catalog["nodes"])
    _require_unique_node_keys(nodes)
    _validate_validator_descriptors(catalog, nodes)
    _validate_topology(catalog, nodes)
    _validate_contract_refs(catalog, nodes)
    for node in nodes:
        _validate_node(node)
    _validate_model_artifact_relations(nodes)
    _validate_quality_contracts(nodes)
    return _build_catalog_indexes(nodes)


def _build_catalog_indexes(nodes: list[dict[str, Any]]) -> WorkflowIndexes:
    """Use the same graph/index semantics as the runtime registry.

    The JSON-schema and catalog-specific checks above provide user-facing
    binding errors; this final pass prevents publication from accepting a shape
    that the runtime registry would interpret differently.
    """

    graph = WorkflowGraph(
        nodes=tuple(
            WorkflowNodeDefinition(
                node_key=cast(str, node["node_key"]),
                execution_kind=cast(str, node["execution_kind"]),
                execution_scope=cast(str, node["execution_scope"]),
                branch_key=cast(str | None, node["branch_key"]),
                entrypoint=cast(bool, node["entrypoint"]),
                dependencies=tuple(cast(list[str], node["dependencies"])),
                input_contract_refs=tuple(cast(list[str], node["input_contract_refs"])),
                output_contract_refs=tuple(cast(list[str], node["output_contract_refs"])),
                binding=cast(Mapping[str, Any], copy.deepcopy(node)),
            )
            for node in nodes
        )
    )
    try:
        return build_workflow_indexes(graph)
    except WorkflowDefinitionError as exc:
        code = exc.code
        if code.startswith("WORKFLOW_"):
            code = "NODE_BINDING_" + code.removeprefix("WORKFLOW_")
        raise NodeGenerationBindingError(code, str(exc)) from exc


def _load_object(path: Path) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
        if len(payload) > MAX_NODE_CATALOG_BYTES:
            raise NodeGenerationBindingError(
                "NODE_BINDING_JSON_TOO_LARGE",
                f"JSON document exceeds size limit: {path.name}",
            )
        value = json.loads(payload.decode("utf-8"))
    except NodeGenerationBindingError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NodeGenerationBindingError(
            "NODE_BINDING_JSON_INVALID",
            f"cannot read JSON object: {path.name}",
        ) from exc
    if not isinstance(value, dict):
        raise NodeGenerationBindingError(
            "NODE_BINDING_JSON_INVALID",
            f"JSON document must be an object: {path.name}",
        )
    return cast(dict[str, Any], value)


def _validate_schema(catalog: dict[str, Any], schema: dict[str, Any]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        cast(Any, validator).validate(catalog)
    except ValidationError as exc:
        path = "/".join(str(part) for part in exc.absolute_path)
        suffix = f" at {path}" if path else ""
        raise NodeGenerationBindingError(
            "NODE_BINDING_SCHEMA_INVALID",
            f"{exc.message}{suffix}",
        ) from exc


def _require_unique_node_keys(nodes: list[dict[str, Any]]) -> None:
    keys = [cast(str, node["node_key"]) for node in nodes]
    if len(keys) != len(set(keys)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_DUPLICATE_NODE_KEY",
            "node binding catalog contains duplicate node_key values",
        )


def _descriptor_identity(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        cast(str, value["key"]),
        cast(str, value["semantic_version"]),
        cast(str, value["implementation_digest"]),
    )


def _validate_validator_descriptors(catalog: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    raw_descriptors = cast(list[dict[str, Any]], catalog["validator_descriptors"])
    identities = [_descriptor_identity(item) for item in raw_descriptors]
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
            if _descriptor_identity(ref) not in descriptor_set:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_VALIDATOR_DESCRIPTOR_UNRESOLVED",
                    f"validator reference is not declared: {ref['key']}",
                )


def _validate_validator_refs(node: dict[str, Any]) -> None:
    refs = cast(list[dict[str, Any]], node["validator_refs"])
    identities = [_descriptor_identity(ref) for ref in refs]
    if len(identities) != len(set(identities)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_VALIDATOR_REF_DUPLICATE",
            f"node contains duplicate validator_refs: {node['node_key']}",
        )


def _validate_topology(catalog: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    node_by_key = {cast(str, node["node_key"]): node for node in nodes}
    for node in nodes:
        key = cast(str, node["node_key"])
        dependencies = cast(list[str], node["dependencies"])
        if len(dependencies) != len(set(dependencies)):
            raise NodeGenerationBindingError(
                "NODE_BINDING_DEPENDENCY_DUPLICATE",
                f"node contains duplicate dependencies: {key}",
            )
        if bool(node["entrypoint"]) != (not dependencies):
            raise NodeGenerationBindingError(
                "NODE_BINDING_ENTRYPOINT_INVALID",
                f"entrypoint does not match dependencies: {key}",
            )
        for dependency in dependencies:
            dependency_node = node_by_key.get(dependency)
            if dependency_node is None:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_DEPENDENCY_MISSING",
                    f"node has missing dependency: {key} -> {dependency}",
                )
            if dependency_node["execution_scope"] != node["execution_scope"]:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_DEPENDENCY_SCOPE_INVALID",
                    f"dependency crosses execution scope: {key} -> {dependency}",
                )
            if dependency_node["branch_key"] != node["branch_key"]:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_DEPENDENCY_BRANCH_INVALID",
                    f"dependency crosses branch: {key} -> {dependency}",
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visited:
            return
        if key in visiting:
            raise NodeGenerationBindingError(
                "NODE_BINDING_DEPENDENCY_CYCLE",
                "workflow node dependencies contain a cycle",
            )
        visiting.add(key)
        for dependency in cast(list[str], node_by_key[key]["dependencies"]):
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in node_by_key:
        visit(key)


def _validate_contract_refs(catalog: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    external = set(cast(list[str], catalog["external_input_contract_refs"]))
    producers: dict[str, list[tuple[str, str, str]]] = {}
    for node in nodes:
        for output_ref in cast(list[str], node["output_contract_refs"]):
            producers.setdefault(output_ref, []).append(
                (
                    cast(str, node["execution_scope"]),
                    cast(str, node["branch_key"]),
                    cast(str, node["node_key"]),
                )
            )
    produced = set(producers)
    collisions = external & produced
    if collisions:
        raise NodeGenerationBindingError(
            "NODE_BINDING_EXTERNAL_CONTRACT_COLLISION",
            f"external inputs collide with published outputs: {sorted(collisions)}",
        )
    for node in nodes:
        inputs = set(cast(list[str], node["input_contract_refs"]))
        missing = inputs - external - produced
        if missing:
            raise NodeGenerationBindingError(
                "NODE_BINDING_CONTRACT_REF_UNRESOLVED",
                f"node contains unresolved input contracts: {node['node_key']}: {sorted(missing)}",
            )
        group = (cast(str, node["execution_scope"]), cast(str, node["branch_key"]))
        for input_ref in inputs - external:
            candidates = producers.get(input_ref, [])
            same_group = [candidate for candidate in candidates if candidate[:2] == group]
            if not same_group and len(candidates) > 1:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_INPUT_PRODUCER_AMBIGUOUS",
                    f"node has an ambiguous cross-branch input: {node['node_key']}: {input_ref}",
                )


def _validate_projection_pointer(pointer: object, *, allow_root: bool = True) -> None:
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


def _validate_value_projection(value: dict[str, Any], *, item: bool = False) -> None:
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
    _validate_projection_pointer(pointer)
    if source == "runtime" and not _is_allowed_runtime_pointer(pointer):
        raise NodeGenerationBindingError(
            "NODE_BINDING_RUNTIME_POINTER_INVALID",
            "runtime projections may expose only trusted runtime values",
        )


def _is_allowed_runtime_pointer(pointer: str) -> bool:
    return pointer in {"/lesson_key", "/reference_assets"} or pointer.startswith("/relation_keys/")


def _validate_projection_declarations(node: dict[str, Any]) -> None:
    output_persistence = node.get("output_persistence")
    if output_persistence is not None:
        output_refs = cast(list[str], node["output_contract_refs"])
        if len(output_refs) != 1:
            raise NodeGenerationBindingError(
                "NODE_BINDING_OUTPUT_CONTRACT_AMBIGUOUS",
                f"output persistence must map to exactly one output contract: {node['node_key']}",
            )
        artifact = cast(dict[str, Any], output_persistence["artifact"])
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
        _validate_value_projection(content)
        relation_keys: set[tuple[str, str]] = set()
        for relation in cast(list[dict[str, Any]], artifact["relations"]):
            source_binding = cast(str, relation["source_binding"])
            if source_binding not in node["input_contract_refs"]:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_RELATION_SOURCE_INVALID",
                    f"relation source is not an input contract: {source_binding}",
                )
            identity_key = (source_binding, cast(str, relation["binding_key"]))
            if identity_key in relation_keys:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_RELATION_DUPLICATE",
                    f"duplicate relation binding: {identity_key[1]}",
                )
            relation_keys.add(identity_key)
            impact_scope = cast(dict[str, Any], relation["impact_scope"])
            if impact_scope["mode"] == "keyed":
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
        package = output_persistence.get("creation_package")
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
        if package is not None:
            if content != {"source": "output", "pointer": ""}:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_CREATION_PACKAGE_CONTENT_INVALID",
                    "creation package nodes must persist the complete validated output",
                )
            _validate_projection_pointer(cast(str, package["items_pointer"]))
            target_rules = cast(dict[str, Any], package["target_rules"])
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
            item_mapping = cast(dict[str, dict[str, Any]], package["item_mapping"])
            for field_name, mapping in item_mapping.items():
                _validate_value_projection(mapping, item=True)
                if field_name == "reference_assets" and mapping not in (
                    {"source": "runtime", "pointer": "/reference_assets"},
                    {"source": "constant", "value": []},
                ):
                    raise NodeGenerationBindingError(
                        "NODE_BINDING_REFERENCE_ASSETS_INVALID",
                        "reference assets must use the trusted runtime set or an empty constant",
                    )


def _validate_model_artifact_relations(nodes: list[dict[str, Any]]) -> None:
    producers: dict[tuple[str, str, str], str] = {}
    for node in nodes:
        if node["execution_kind"] != "model_generation":
            continue
        group = (cast(str, node["execution_scope"]), cast(str, node["branch_key"]))
        for output_ref in cast(list[str], node["output_contract_refs"]):
            producers[(*group, output_ref)] = cast(str, node["node_key"])

    for node in nodes:
        if node["execution_kind"] != "model_generation":
            continue
        group = (cast(str, node["execution_scope"]), cast(str, node["branch_key"]))
        required = {
            input_ref
            for input_ref in cast(list[str], node["input_contract_refs"])
            if producers.get((*group, input_ref)) not in {None, node["node_key"]}
        }
        persistence = cast(dict[str, Any], node["output_persistence"])
        artifact = cast(dict[str, Any], persistence["artifact"])
        declared = {
            relation["source_binding"]
            for relation in cast(list[dict[str, Any]], artifact["relations"])
        }
        missing = required - declared
        if missing:
            raise NodeGenerationBindingError(
                "NODE_BINDING_RELATION_SOURCE_MISSING",
                f"model node is missing Artifact relations: {node['node_key']}: {sorted(missing)}",
            )


def _validate_quality_contracts(nodes: list[dict[str, Any]]) -> None:
    report_producers: dict[tuple[str, str, str], dict[str, Any]] = {}
    contract_producers: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for node in nodes:
        scope_branch = (
            cast(str, node["execution_scope"]),
            cast(str, node["branch_key"]),
        )
        for output_ref in cast(list[str], node["output_contract_refs"]):
            contract_producers.setdefault((*scope_branch, output_ref), []).append(node)
    for node in nodes:
        reports = [
            ref
            for ref in cast(list[str], node["output_contract_refs"])
            if ref.startswith("report:")
        ]
        persistence = node.get("quality_report_persistence")
        if persistence is not None:
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
            validators = {
                _descriptor_identity(ref)
                for ref in cast(list[dict[str, Any]], persistence["validator_refs"])
            }
            node_validators = {
                _descriptor_identity(ref)
                for ref in cast(list[dict[str, Any]], node["validator_refs"])
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
            for value in cast(dict[str, dict[str, Any]], persistence["mapping"]).values():
                if value.get("source") != "output":
                    raise NodeGenerationBindingError(
                        "NODE_BINDING_QUALITY_MAPPING_INVALID",
                        f"quality report mappings must use validator output: {node['node_key']}",
                    )
                _validate_value_projection(value)
            scope_branch = (
                cast(str, node["execution_scope"]),
                cast(str, node["branch_key"]),
            )
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
            report_key = (
                cast(str, node["execution_scope"]),
                cast(str, node["branch_key"]),
                report_ref,
            )
            if report_key in report_producers:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_QUALITY_REPORT_DUPLICATE",
                    f"report has multiple producers: {report_ref}",
                )
            report_producers[report_key] = node

    consumed_reports: set[tuple[str, str, str]] = set()
    for node in nodes:
        if node["execution_kind"] != "human_gate":
            continue
        requirement = cast(dict[str, Any], node["quality_requirement"])
        if requirement["mode"] != "reports":
            continue
        report_refs = cast(list[str], requirement["report_refs"])
        if len(report_refs) != len(set(report_refs)):
            raise NodeGenerationBindingError(
                "NODE_BINDING_QUALITY_GATE_INVALID",
                f"quality gate contains duplicate report refs: {node['node_key']}",
            )
        for report_ref in report_refs:
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
            if report_key in consumed_reports:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_QUALITY_GATE_INVALID",
                    f"quality report has multiple gates: {report_ref}",
                )
            consumed_reports.add(report_key)
    orphaned = set(report_producers) - consumed_reports
    if orphaned:
        raise NodeGenerationBindingError(
            "NODE_BINDING_QUALITY_REPORT_ORPHANED",
            f"quality reports have no gate: {sorted(key[2] for key in orphaned)}",
        )


def _validate_node(node: dict[str, Any]) -> None:
    _validate_execution_kind_declaration(node)
    _validate_prompt_exposure(node)
    _validate_unique_strings(node, "input_contract_refs", "NODE_BINDING_CONTRACT_REF_DUPLICATE")
    _validate_unique_strings(node, "output_contract_refs", "NODE_BINDING_CONTRACT_REF_DUPLICATE")
    _validate_validator_refs(node)
    _validate_instruction_policy(cast(dict[str, Any], node["instruction_policy"]))
    _validate_context_policy(cast(dict[str, Any], node["context_policy"]))
    _validate_reference_asset_policy(cast(dict[str, Any], node["reference_asset_policy"]))
    _validate_projection_declarations(node)
    if node["execution_kind"] == "model_generation":
        validate_model_capability(cast(str, node["model_capability"]))
        if not node["validator_refs"]:
            raise NodeGenerationBindingError(
                "NODE_BINDING_VALIDATOR_REQUIRED",
                f"model node requires a validator: {node['node_key']}",
            )
    elif node["execution_kind"] == "deterministic":
        _validate_executor(cast(str, node["executor_ref"]))
    elif not cast(dict[str, Any], node["approval_policy"])["required_before_downstream"]:
        raise NodeGenerationBindingError(
            "NODE_BINDING_HUMAN_GATE_INVALID",
            f"human gate must block downstream execution: {node['node_key']}",
        )


def _validate_execution_kind_declaration(node: dict[str, Any]) -> None:
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
                "output_persistence",
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


def validate_model_capability(capability: str) -> None:
    """Require a registered logical capability at the workflow contract boundary."""

    if capability not in REGISTERED_MODEL_CAPABILITIES:
        raise NodeGenerationBindingError(
            "NODE_BINDING_CAPABILITY_FORBIDDEN",
            f"model capability must be registered and provider-neutral: {capability}",
        )


def _validate_executor(executor_ref: str) -> None:
    tokens = set(TOKEN_SPLIT.split(executor_ref.lower()))
    if tokens & FORBIDDEN_EXECUTOR_TOKENS:
        raise NodeGenerationBindingError(
            "NODE_BINDING_EXECUTOR_FORBIDDEN",
            f"executor_ref must identify a registered safe executor: {executor_ref}",
        )


def _validate_unique_strings(node: dict[str, Any], field: str, code: str) -> None:
    values = cast(list[str], node[field])
    if len(values) != len(set(values)):
        raise NodeGenerationBindingError(
            code,
            f"node contains duplicate {field}: {node['node_key']}",
        )
