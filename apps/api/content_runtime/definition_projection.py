"""Deterministic runtime projections for content-definition field trees."""

from __future__ import annotations

from typing import Any, cast

from jsonschema import Draft202012Validator

_STRING_TYPES = {"text", "rich_text", "color", "math"}
_ARRAY_TYPES = {"list", "table", "repeatable"}
_OBJECT_TYPES = {"object", "group", "rubric", "timeline"}


def build_content_json_schema(spec: dict[str, Any]) -> dict[str, Any]:
    """Compile a ContentDefinition field tree into an executable JSON Schema."""

    schema = _object_schema(cast(list[dict[str, Any]], spec["fields"]))
    schema.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": cast(str, spec["title"]),
        }
    )
    description = spec.get("description")
    if isinstance(description, str):
        schema["description"] = description
    Draft202012Validator.check_schema(schema)
    return schema


def _object_schema(fields: list[dict[str, Any]]) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            cast(str, field["field_key"]): _field_schema(field) for field in fields
        },
    }
    required = [cast(str, field["field_key"]) for field in fields if field["required"]]
    if required:
        schema["required"] = required
    return schema


def _field_schema(field: dict[str, Any]) -> dict[str, Any]:
    field_type = cast(str, field["type"])
    children = cast(list[dict[str, Any]], field.get("children", []))
    if field_type in _STRING_TYPES:
        schema: dict[str, Any] = {"type": "string"}
    elif field_type == "number":
        schema = {"type": "number"}
    elif field_type == "boolean":
        schema = {"type": "boolean"}
    elif field_type == "enum":
        options = cast(list[dict[str, Any]], field.get("options", []))
        schema = {"enum": [option["value"] for option in options]} if options else {}
    elif field_type in _ARRAY_TYPES:
        schema = {"type": "array", "items": _object_schema(children) if children else {}}
    elif field_type in _OBJECT_TYPES:
        schema = _object_schema(children) if children else {"type": "object"}
    elif field_type in {"reference", "asset"}:
        schema = {"anyOf": [{"type": "string"}, {"type": "object"}]}
    else:
        raise ValueError(f"unsupported content definition field type: {field_type}")

    schema["title"] = cast(str, field["label"])
    description = field.get("description")
    if isinstance(description, str):
        schema["description"] = description
    if "default_value" in field:
        schema["default"] = field["default_value"]
    if field_type in _ARRAY_TYPES:
        if "min_items" in field:
            schema["minItems"] = field["min_items"]
        if "max_items" in field:
            schema["maxItems"] = field["max_items"]
    return schema
