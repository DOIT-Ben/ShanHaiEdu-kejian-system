"""Deterministic runtime projections for content-definition field trees."""

from __future__ import annotations

from typing import Any, cast

from jsonschema import Draft202012Validator

_STRING_TYPES = {"text", "rich_text", "color", "math"}
_ARRAY_TYPES = {"list", "table", "repeatable"}
_OBJECT_TYPES = {"object", "group", "rubric", "timeline"}
_SCHEMA_RULES = {
    "minimum": "minimum",
    "maximum": "maximum",
    "min_length": "minLength",
    "max_length": "maxLength",
    "pattern": "pattern",
    "min_items": "minItems",
    "max_items": "maxItems",
}
_CUSTOM_RULES = {"equals_repeatable_count"}


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


def build_content_validation_rules(spec: dict[str, Any]) -> dict[str, Any]:
    """Normalize non-Schema field rules without losing their source paths."""

    field_rules: list[dict[str, Any]] = []
    _collect_field_rules(cast(list[dict[str, Any]], spec["fields"]), [], field_rules)
    return {"field_rules": field_rules}


def validate_content_rules(
    rules_json: dict[str, Any],
    content: dict[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate cross-field rules that Draft 2020-12 cannot express."""

    errors: list[dict[str, Any]] = []
    for entry in cast(list[dict[str, Any]], rules_json.get("field_rules", [])):
        field_path = cast(list[str], entry["field_path"])
        value = _resolve_path(content, field_path)
        for rule in cast(list[dict[str, Any]], entry["rules"]):
            target_key = rule.get("equals_repeatable_count")
            if not isinstance(target_key, str):
                continue
            target_path = [*field_path[:-1], target_key]
            target = _resolve_path(content, target_path)
            if (
                isinstance(value, int | float)
                and not isinstance(value, bool)
                and isinstance(target, list)
                and value != len(target)
            ):
                errors.append(
                    {
                        "path": field_path,
                        "message": (f"must equal the number of items in {'.'.join(target_path)}"),
                    }
                )
    return errors


def _object_schema(fields: list[dict[str, Any]]) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {cast(str, field["field_key"]): _field_schema(field) for field in fields},
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
    for rule in cast(list[dict[str, Any]], field.get("validation_rules", [])):
        _apply_schema_rule(schema, rule)
    return schema


def _apply_schema_rule(schema: dict[str, Any], rule: dict[str, Any]) -> None:
    if len(rule) != 1:
        raise ValueError("content definition validation rules must contain one operator")
    operator, value = next(iter(rule.items()))
    if operator in _SCHEMA_RULES:
        schema[_SCHEMA_RULES[operator]] = value
    elif operator not in _CUSTOM_RULES:
        raise ValueError(f"unsupported content definition validation rule: {operator}")


def _collect_field_rules(
    fields: list[dict[str, Any]],
    parent_path: list[str],
    output: list[dict[str, Any]],
) -> None:
    for field in fields:
        path = [*parent_path, cast(str, field["field_key"])]
        rules = cast(list[dict[str, Any]], field.get("validation_rules", []))
        for rule in rules:
            _apply_schema_rule({}, rule)
            if parent_path and any(operator in _CUSTOM_RULES for operator in rule):
                raise ValueError("nested cross-field validation rules are not supported")
        if rules:
            output.append({"field_path": path, "rules": rules})
        _collect_field_rules(
            cast(list[dict[str, Any]], field.get("children", [])),
            path,
            output,
        )


def _resolve_path(content: object, path: list[str]) -> object:
    current = content
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
