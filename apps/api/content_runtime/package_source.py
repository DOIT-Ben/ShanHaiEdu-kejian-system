"""Trusted loader for the repository's built-in courseware release source."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from apps.api.content_runtime.definition_projection import build_content_json_schema
from workflow.content_package import canonical_json_sha256, validate_content_package
from workflow.node_generation_binding import load_workflow_node_catalog
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

_CREATION_PACKAGE_MAPPING_TYPES = {
    "item_key": frozenset({"string"}),
    "position": frozenset({"integer"}),
    "title": frozenset({"string"}),
    "business_prompt": frozenset({"string"}),
    "prompt": frozenset({"object"}),
    "reference_assets": frozenset({"array"}),
    "output_spec": frozenset({"object"}),
    "target_slot": frozenset({"string"}),
    "consistency_key": frozenset({"string", "null"}),
}
_TARGET_SLOT_PATTERN = r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$"


class ContentPublicationConflict(ValueError):
    """Raised when immutable publication content or identities disagree."""


@dataclass(frozen=True, slots=True)
class BuiltinCoursewareReleaseSource:
    manifest: dict[str, Any]
    items: dict[str, dict[str, Any]]
    manifest_entries: dict[str, dict[str, Any]]
    workflow_catalog: dict[str, Any]
    package_checksum: str
    workflow_checksum: str

    @property
    def package_key(self) -> str:
        return cast(str, self.manifest["package_key"])

    @property
    def package_name(self) -> str:
        return cast(str, self.manifest["name"])

    @property
    def semantic_version(self) -> str:
        return cast(str, self.manifest["semantic_version"])

    @property
    def runtime_constraint(self) -> str:
        return cast(str, self.manifest["runtime_constraint"])

    @property
    def release_key(self) -> str:
        return f"{self.package_key}@{self.semantic_version}"

    @property
    def workflow_key(self) -> str:
        return cast(str, self.workflow_catalog["workflow_key"])

    @property
    def workflow_input_contract(self) -> dict[str, str]:
        return {
            "package_key": self.package_key,
            "package_semantic_version": self.semantic_version,
            "package_checksum": self.package_checksum,
            "workflow_checksum": self.workflow_checksum,
        }

    @property
    def content_definition_count(self) -> int:
        return sum(
            entry["kind"] == "content_definition" for entry in self.manifest_entries.values()
        )


def load_builtin_courseware_release(root: Path) -> BuiltinCoursewareReleaseSource:
    """Load and cross-check the repository's one authoritative built-in release source."""

    contracts_root = root / "contracts"
    package = validate_content_package(
        contracts_root / "fixtures/primary-math-courseware-package",
        contracts_root=contracts_root,
    )
    catalog = load_workflow_node_catalog(
        contracts_root / "fixtures/workflow-node-generation-bindings/primary-math-courseware.json",
        schema_path=contracts_root / "workflow-node-generation-binding.schema.json",
    )
    # Publication and execution must validate the exact same graph shape.  The
    # binding validator checks package-local semantics; the runtime registry
    # additionally proves that the persisted graph is executable without
    # falling back to a legacy catalog or hard-coded contract list.
    BUILTIN_WORKFLOW_REGISTRY.load(catalog.catalog)
    manifest_entries = {
        cast(str, entry["item_key"]): entry
        for entry in cast(list[dict[str, Any]], package.manifest["items"])
    }
    _validate_catalog_content_definitions(catalog.catalog, package.items, manifest_entries)
    entrypoints = set(cast(list[str], package.manifest["entrypoints"]))
    model_template_refs = {
        cast(str, node["generation_template_ref"]["item_key"])
        for node in cast(list[dict[str, Any]], catalog.catalog["nodes"])
        if node["execution_kind"] == "model_generation"
    }
    if package.manifest["semantic_version"] != catalog.catalog["semantic_version"]:
        raise ContentPublicationConflict("package and workflow catalog versions differ")
    if entrypoints != model_template_refs:
        raise ContentPublicationConflict("package entrypoints and model node bindings differ")
    return BuiltinCoursewareReleaseSource(
        manifest=package.manifest,
        items=dict(package.items),
        manifest_entries=manifest_entries,
        workflow_catalog=catalog.catalog,
        package_checksum=canonical_json_sha256(package.manifest),
        workflow_checksum=catalog.content_hash,
    )


def _validate_catalog_content_definitions(
    catalog: dict[str, Any],
    items: Mapping[str, dict[str, Any]],
    manifest_entries: Mapping[str, dict[str, Any]],
) -> None:
    for node in cast(list[dict[str, Any]], catalog["nodes"]):
        if node["execution_kind"] != "model_generation":
            continue
        template_key = cast(str, node["generation_template_ref"]["item_key"])
        template = items.get(template_key)
        if template is None or manifest_entries[template_key]["kind"] != "generation_template":
            raise ContentPublicationConflict(
                f"generation template is missing from the published package: {template_key}"
            )
        spec = cast(dict[str, Any], template.get("spec", {}))
        output_ref = spec.get("output_definition_ref")
        artifact_ref = node["output_persistence"]["artifact"]["content_definition_ref"]
        if output_ref != artifact_ref:
            raise ContentPublicationConflict(
                f"artifact output definition disagrees with generation template: {node['node_key']}"
            )
        output_key = cast(str, artifact_ref["item_key"])
        if output_key not in items or manifest_entries[output_key]["kind"] != "content_definition":
            raise ContentPublicationConflict(
                f"content definition is missing from the published package: {output_key}"
            )
        _validate_creation_package_projection(node, items[output_key])


def _validate_creation_package_projection(
    node: dict[str, Any],
    output_definition: dict[str, Any],
) -> None:
    output_persistence = cast(dict[str, Any], node["output_persistence"])
    raw_package = output_persistence.get("creation_package")
    if raw_package is None:
        return
    package = cast(dict[str, Any], raw_package)
    output_spec = cast(dict[str, Any], output_definition["spec"])
    output_schema = build_content_json_schema(output_spec)
    node_key = cast(str, node["node_key"])
    items_pointer = cast(str, package["items_pointer"])
    item_schema = _require_creation_package_item_schema(
        output_schema,
        node_key=node_key,
        items_pointer=items_pointer,
    )
    item_mapping = cast(dict[str, dict[str, Any]], package["item_mapping"])
    for mapping_name in sorted(item_mapping):
        _validate_item_mapping_projection(
            node,
            node_key=node_key,
            mapping_name=mapping_name,
            projection=item_mapping[mapping_name],
            output_schema=output_schema,
            item_schema=item_schema,
        )


def _require_creation_package_item_schema(
    output_schema: Mapping[str, Any],
    *,
    node_key: str,
    items_pointer: str,
) -> Mapping[str, Any]:
    items_schema = _schema_at_pointer(output_schema, items_pointer)
    if items_schema is None or items_schema.get("type") != "array":
        raise ContentPublicationConflict(
            "creation package items_pointer does not resolve to a required object array: "
            f"{node_key} {items_pointer}"
        )
    min_items, max_items = items_schema.get("minItems"), items_schema.get("maxItems")
    if not (
        type(min_items) is int and type(max_items) is int and 1 <= min_items <= max_items <= 100
    ):
        raise ContentPublicationConflict(
            f"creation package items array bounds are unsafe: {node_key} {items_pointer}"
        )
    raw_item_schema = items_schema.get("items")
    if not isinstance(raw_item_schema, Mapping):
        raise ContentPublicationConflict(
            "creation package items_pointer does not resolve to a required object array: "
            f"{node_key} {items_pointer}"
        )
    item_schema = cast(Mapping[str, Any], raw_item_schema)
    if item_schema.get("type") != "object":
        raise ContentPublicationConflict(
            "creation package items_pointer does not resolve to a required object array: "
            f"{node_key} {items_pointer}"
        )
    return item_schema


def _validate_item_mapping_projection(
    node: Mapping[str, Any],
    *,
    node_key: str,
    mapping_name: str,
    projection: Mapping[str, Any],
    output_schema: Mapping[str, Any],
    item_schema: Mapping[str, Any],
) -> None:
    source = projection.get("source")
    source_schema = (
        item_schema if source == "item" else output_schema if source == "output" else None
    )
    projected_schema: Mapping[str, Any] | None = None
    if source_schema is not None:
        location = projection.get("pointer")
        projected_schema = (
            _schema_at_pointer(source_schema, location) if isinstance(location, str) else None
        )
        if projected_schema is None:
            raise ContentPublicationConflict(
                "creation package item_mapping pointer does not resolve "
                "to a required output field: "
                f"{node_key} {mapping_name} {source} {location}"
            )
        actual_types = _schema_json_types(projected_schema)
    else:
        actual_types, location = _non_schema_projection_types(node, projection)
    if not _mapping_types_are_compatible(mapping_name, actual_types):
        raise ContentPublicationConflict(
            "creation package item_mapping type is incompatible with the output definition: "
            f"{node_key} {mapping_name} {source} {location}"
        )
    if projected_schema is None or actual_types is None or "string" not in actual_types:
        return
    min_length, max_length = projected_schema.get("minLength"), projected_schema.get("maxLength")
    limit = {"business_prompt": 50_000, "title": 255}.get(mapping_name, 160)
    if not (
        type(min_length) is int
        and type(max_length) is int
        and 1 <= min_length <= max_length <= limit
    ):
        raise ContentPublicationConflict(
            "creation package string mapping bounds are unsafe: "
            f"{node_key} {mapping_name} {source} {location}"
        )
    if mapping_name == "target_slot" and projected_schema.get("pattern") != _TARGET_SLOT_PATTERN:
        raise ContentPublicationConflict(
            "creation package target_slot mapping lacks the required semantic pattern: "
            f"{node_key} {source} {location}"
        )


def _non_schema_projection_types(
    node: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> tuple[frozenset[str] | None, object]:
    source = projection.get("source")
    if source == "constant":
        return frozenset({_json_value_type(projection.get("value"))}), "<constant>"
    if source == "intrinsic":
        location = projection.get("name")
        types = frozenset({"integer"}) if location == "item_position" else None
        return types, location
    if source == "runtime":
        location = projection.get("pointer")
        return _runtime_projection_types(node, location), location
    return None, "<unknown>"


def _schema_at_pointer(
    schema: Mapping[str, Any],
    pointer: str,
) -> Mapping[str, Any] | None:
    parts = _decode_pointer(pointer)
    if parts is None:
        return None
    current = schema
    for part in parts:
        raw_child: object | None
        if current.get("type") == "object":
            raw_properties = current.get("properties")
            raw_required = current.get("required")
            if not isinstance(raw_properties, Mapping) or not isinstance(raw_required, list):
                return None
            required = cast(list[object], raw_required)
            if part not in required:
                return None
            properties = cast(Mapping[str, object], raw_properties)
            raw_child = properties.get(part)
        elif current.get("type") == "array" and _is_canonical_array_index(part):
            min_items = current.get("minItems")
            if type(min_items) is not int or min_items <= int(part):
                return None
            raw_child = current.get("items")
        else:
            return None
        if not isinstance(raw_child, Mapping):
            return None
        current = cast(Mapping[str, Any], raw_child)
    return current


def _decode_pointer(pointer: str) -> tuple[str, ...] | None:
    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        return None
    return tuple(part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:])


def _is_canonical_array_index(value: str) -> bool:
    return value == "0" or (value.isascii() and value.isdigit() and not value.startswith("0"))


def _mapping_types_are_compatible(
    mapping_name: str,
    actual: frozenset[str] | None,
) -> bool:
    expected = _CREATION_PACKAGE_MAPPING_TYPES.get(mapping_name)
    return expected is not None and actual is not None and actual <= expected


def _runtime_projection_types(
    node: Mapping[str, Any],
    pointer: object,
) -> frozenset[str] | None:
    if pointer == "/reference_assets":
        return frozenset({"array"})
    if pointer == "/lesson_key":
        return (
            frozenset({"string"})
            if node.get("execution_scope") == "lesson_unit"
            else frozenset({"null"})
        )
    return None


def _schema_json_types(schema: Mapping[str, Any]) -> frozenset[str] | None:
    raw_type = schema.get("type")
    if isinstance(raw_type, str):
        return frozenset({raw_type})
    if isinstance(raw_type, list):
        type_values = cast(list[object], raw_type)
        if type_values and all(isinstance(value, str) for value in type_values):
            return frozenset(cast(list[str], type_values))
    for keyword in ("anyOf", "oneOf"):
        raw_alternatives = schema.get(keyword)
        if not isinstance(raw_alternatives, list) or not raw_alternatives:
            continue
        types: set[str] = set()
        for raw_alternative in cast(list[object], raw_alternatives):
            if not isinstance(raw_alternative, Mapping):
                return None
            alternative_types = _schema_json_types(cast(Mapping[str, Any], raw_alternative))
            if alternative_types is None:
                return None
            types.update(alternative_types)
        return frozenset(types)
    raw_enum = schema.get("enum")
    if isinstance(raw_enum, list) and raw_enum:
        enum_values = cast(list[object], raw_enum)
        return frozenset(_json_value_type(value) for value in enum_values)
    if "const" in schema:
        return frozenset({_json_value_type(schema["const"])})
    return None


def _json_value_type(value: object) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is float:
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        return "array"
    return "unknown"
