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
    nodes = cast(list[dict[str, Any]], catalog["nodes"])
    _require_unique_node_keys(nodes)
    _validate_validator_descriptors(catalog, nodes)
    _validate_topology(catalog, nodes)
    _validate_contract_refs(catalog, nodes)
    for node in nodes:
        _validate_node(node)
    _validate_quality_contracts(nodes)
    indexes = _build_catalog_indexes(nodes)
    canonical = canonical_catalog_json(catalog)
    return ValidatedWorkflowNodeCatalog(
        catalog=catalog,
        canonical_json=canonical,
        content_hash=hashlib.sha256(canonical).hexdigest(),
        indexes=indexes,
    )


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


def _validate_validator_descriptors(
    catalog: dict[str, Any], nodes: list[dict[str, Any]]
) -> None:
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
    produced = {
        output_ref
        for node in nodes
        for output_ref in cast(list[str], node["output_contract_refs"])
    }
    for node in nodes:
        missing = set(cast(list[str], node["input_contract_refs"])) - external - produced
        if missing:
            raise NodeGenerationBindingError(
                "NODE_BINDING_CONTRACT_REF_UNRESOLVED",
                f"node contains unresolved input contracts: {node['node_key']}: {sorted(missing)}",
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
    if any(ord(char) < 0x20 for char in pointer):
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROJECTION_POINTER_INVALID",
            "projection pointer contains a control character",
        )
    for token in pointer.split("/")[1:]:
        if "*" in token or token == "-" or "[" in token or "]" in token:
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
    return (
        pointer in {"/lesson_key", "/reference_assets"}
        or pointer.startswith("/relation_keys/")
    )


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
        expected_strategy = (
            "project_singleton" if scope == "project" else "lesson_unit_singleton"
        )
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
            _validate_projection_pointer(cast(str, package["items_pointer"]))
            item_mapping = cast(dict[str, dict[str, Any]], package["item_mapping"])
            for field_name, mapping in item_mapping.items():
                _validate_value_projection(mapping, item=True)
                if field_name == "reference_assets" and mapping.get("source") == "constant":
                    value = mapping.get("value")
                    if not isinstance(value, list):
                        raise NodeGenerationBindingError(
                            "NODE_BINDING_REFERENCE_ASSETS_INVALID",
                            "constant reference_assets must be an array",
                        )
                    for asset in value:
                        if (
                            not isinstance(asset, dict)
                            or set(asset) != {"asset_version_id", "role"}
                            or not isinstance(asset.get("asset_version_id"), str)
                            or not isinstance(asset.get("role"), str)
                            or not asset["asset_version_id"].strip()
                            or not asset["role"].strip()
                        ):
                            raise NodeGenerationBindingError(
                                "NODE_BINDING_REFERENCE_ASSETS_INVALID",
                                "constant reference assets must contain an ID and role",
                            )


def _validate_quality_contracts(nodes: list[dict[str, Any]]) -> None:
    report_producers: dict[str, dict[str, Any]] = {}
    for node in nodes:
        reports = [
            ref for ref in cast(list[str], node["output_contract_refs"])
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
            for value in cast(dict[str, dict[str, Any]], persistence["mapping"]).values():
                _validate_value_projection(value)
            if report_ref in report_producers:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_QUALITY_REPORT_DUPLICATE",
                    f"report has multiple producers: {report_ref}",
                )
            report_producers[report_ref] = node

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
            if report_ref not in node["input_contract_refs"]:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_QUALITY_GATE_INVALID",
                    f"quality gate does not consume report: {node['node_key']}",
                )
            if report_ref not in report_producers:
                raise NodeGenerationBindingError(
                    "NODE_BINDING_QUALITY_REPORT_UNRESOLVED",
                    f"quality gate references an undeclared report: {report_ref}",
                )
def _validate_node(node: dict[str, Any]) -> None:
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
