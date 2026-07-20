"""Publication-time validation for CreationPackage output projections."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

from apps.api.content_runtime.definition_projection import build_content_json_schema

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


def validate_creation_package_projection(
    node: dict[str, Any],
    output_definition: dict[str, Any],
    *,
    conflict_type: type[ValueError],
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
        conflict_type=conflict_type,
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
            conflict_type=conflict_type,
        )


def _require_creation_package_item_schema(
    output_schema: Mapping[str, Any],
    *,
    node_key: str,
    items_pointer: str,
    conflict_type: type[ValueError],
) -> Mapping[str, Any]:
    items_schema = _schema_at_pointer(output_schema, items_pointer)
    if items_schema is None or items_schema.get("type") != "array":
        raise conflict_type(
            "creation package items_pointer does not resolve to a required object array: "
            f"{node_key} {items_pointer}"
        )
    min_items, max_items = items_schema.get("minItems"), items_schema.get("maxItems")
    if not (
        type(min_items) is int and type(max_items) is int and 1 <= min_items <= max_items <= 100
    ):
        raise conflict_type(
            f"creation package items array bounds are unsafe: {node_key} {items_pointer}"
        )
    raw_item_schema = items_schema.get("items")
    if not isinstance(raw_item_schema, Mapping):
        raise conflict_type(
            "creation package items_pointer does not resolve to a required object array: "
            f"{node_key} {items_pointer}"
        )
    item_schema = cast(Mapping[str, Any], raw_item_schema)
    if item_schema.get("type") != "object":
        raise conflict_type(
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
    conflict_type: type[ValueError],
) -> None:
    source = projection.get("source")
    projected_schema, actual_types, location = _resolve_projection(
        node,
        node_key=node_key,
        mapping_name=mapping_name,
        projection=projection,
        output_schema=output_schema,
        item_schema=item_schema,
        conflict_type=conflict_type,
    )
    if not _mapping_types_are_compatible(mapping_name, actual_types):
        raise conflict_type(
            "creation package item_mapping type is incompatible with the output definition: "
            f"{node_key} {mapping_name} {source} {location}"
        )
    _validate_constant_position(
        node_key=node_key,
        mapping_name=mapping_name,
        projection=projection,
        conflict_type=conflict_type,
    )
    _validate_string_mapping_bounds(
        node_key=node_key,
        mapping_name=mapping_name,
        projection=projection,
        location=location,
        actual_types=actual_types,
        projected_schema=projected_schema,
        conflict_type=conflict_type,
    )


def _resolve_projection(
    node: Mapping[str, Any],
    *,
    node_key: str,
    mapping_name: str,
    projection: Mapping[str, Any],
    output_schema: Mapping[str, Any],
    item_schema: Mapping[str, Any],
    conflict_type: type[ValueError],
) -> tuple[Mapping[str, Any] | None, frozenset[str] | None, object]:
    source = projection.get("source")
    source_schema = (
        item_schema if source == "item" else output_schema if source == "output" else None
    )
    if source_schema is None:
        actual_types, location = _non_schema_projection_types(node, projection)
        return None, actual_types, location
    location = projection.get("pointer")
    projected_schema = (
        _schema_at_pointer(source_schema, location) if isinstance(location, str) else None
    )
    if projected_schema is None:
        raise conflict_type(
            "creation package item_mapping pointer does not resolve "
            "to a required output field: "
            f"{node_key} {mapping_name} {source} {location}"
        )
    return projected_schema, _schema_json_types(projected_schema), location


def _validate_constant_position(
    *,
    node_key: str,
    mapping_name: str,
    projection: Mapping[str, Any],
    conflict_type: type[ValueError],
) -> None:
    if mapping_name != "position" or projection.get("source") != "constant":
        return
    value = projection.get("value")
    if type(value) is not int or not 1 <= value <= 100:
        raise conflict_type(
            f"creation package constant position is outside package bounds: {node_key} {value}"
        )


def _validate_string_mapping_bounds(
    *,
    node_key: str,
    mapping_name: str,
    projection: Mapping[str, Any],
    location: object,
    actual_types: frozenset[str] | None,
    projected_schema: Mapping[str, Any] | None,
    conflict_type: type[ValueError],
) -> None:
    if actual_types is None or "string" not in actual_types:
        return
    limit = {"business_prompt": 50_000, "title": 255}.get(mapping_name, 160)
    if projected_schema is None:
        _validate_constant_string_mapping(
            node_key=node_key,
            mapping_name=mapping_name,
            projection=projection,
            location=location,
            limit=limit,
            conflict_type=conflict_type,
        )
        return
    _validate_schema_string_mapping(
        node_key=node_key,
        mapping_name=mapping_name,
        source=projection.get("source"),
        location=location,
        limit=limit,
        projected_schema=projected_schema,
        conflict_type=conflict_type,
    )


def _validate_constant_string_mapping(
    *,
    node_key: str,
    mapping_name: str,
    projection: Mapping[str, Any],
    location: object,
    limit: int,
    conflict_type: type[ValueError],
) -> None:
    source = projection.get("source")
    value = projection.get("value")
    if source != "constant" or type(value) is not str or not value.strip() or len(value) > limit:
        raise conflict_type(
            "creation package string mapping bounds are unsafe: "
            f"{node_key} {mapping_name} {source} {location}"
        )
    if mapping_name == "target_slot" and re.fullmatch(_TARGET_SLOT_PATTERN, value) is None:
        raise conflict_type(
            "creation package target_slot mapping lacks the required semantic pattern: "
            f"{node_key} {source} {location}"
        )


def _validate_schema_string_mapping(
    *,
    node_key: str,
    mapping_name: str,
    source: object,
    location: object,
    limit: int,
    projected_schema: Mapping[str, Any],
    conflict_type: type[ValueError],
) -> None:
    min_length = projected_schema.get("minLength")
    max_length = projected_schema.get("maxLength")
    if not (
        type(min_length) is int
        and type(max_length) is int
        and 1 <= min_length <= max_length <= limit
    ):
        raise conflict_type(
            "creation package string mapping bounds are unsafe: "
            f"{node_key} {mapping_name} {source} {location}"
        )
    if mapping_name == "target_slot" and projected_schema.get("pattern") != _TARGET_SLOT_PATTERN:
        raise conflict_type(
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
