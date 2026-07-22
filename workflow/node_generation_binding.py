"""Validation facade for declarative workflow node generation binding catalogs."""

from __future__ import annotations

import copy
import hashlib
import json
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
from workflow.node_generation_binding_common import (
    REGISTERED_MODEL_CAPABILITIES,
    NodeGenerationBindingError,
    require_unique_node_keys,
    validate_model_capability,
    validate_validator_descriptors,
)
from workflow.node_generation_binding_node import validate_node
from workflow.node_generation_binding_quality import validate_quality_contracts
from workflow.node_generation_binding_topology import (
    validate_contract_refs,
    validate_model_artifact_relations,
    validate_topology,
)

MAX_NODE_CATALOG_BYTES = 5_000_000

__all__ = (
    "REGISTERED_MODEL_CAPABILITIES",
    "NodeGenerationBindingError",
    "ValidatedWorkflowNodeCatalog",
    "canonical_catalog_json",
    "load_workflow_node_catalog",
    "validate_model_capability",
    "validate_workflow_node_catalog",
    "validate_workflow_node_catalog_semantics",
)


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
    require_unique_node_keys(nodes)
    validate_validator_descriptors(catalog, nodes)
    validate_topology(nodes)
    validate_contract_refs(catalog, nodes)
    for node in nodes:
        validate_node(node)
    validate_model_artifact_relations(nodes)
    validate_quality_contracts(nodes)
    return _build_catalog_indexes(nodes)


def _build_catalog_indexes(nodes: list[dict[str, Any]]) -> WorkflowIndexes:
    """Build indexes using the runtime registry's graph semantics."""

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
                optional_input_contract_refs=tuple(
                    cast(list[str], node.get("optional_input_contract_refs", []))
                ),
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
