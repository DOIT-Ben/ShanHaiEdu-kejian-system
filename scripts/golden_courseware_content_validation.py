"""Validate projected golden outputs against content-definition field trees."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NoReturn, cast

Fail = Callable[[str, str], NoReturn]


def _type_matches(value: object, field: dict[str, Any]) -> bool:
    field_type = cast(str, field["type"])
    if field_type in {"text", "rich_text", "color", "math"}:
        return isinstance(value, str)
    if field_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if field_type == "boolean":
        return isinstance(value, bool)
    if field_type in {"list", "table", "repeatable"}:
        return isinstance(value, list)
    if field_type in {"object", "group", "rubric", "timeline"}:
        return isinstance(value, dict)
    if field_type == "enum":
        options = cast(list[dict[str, Any]], field.get("options", []))
        return not options or value in {option["value"] for option in options}
    if field_type in {"reference", "asset"}:
        return isinstance(value, str | dict)
    return True


def _input_type_matches(value: object, field: dict[str, Any]) -> bool:
    value_type = cast(str, field["value_type"])
    if value_type in {"text", "rich_text", "color", "math"}:
        return isinstance(value, str)
    if value_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type in {"list", "table"}:
        return isinstance(value, list)
    if value_type == "enum":
        options = cast(list[dict[str, Any]], field.get("options", []))
        return not options or value in {option["value"] for option in options}
    if value_type in {"reference", "asset"}:
        return isinstance(value, str | dict | list)
    return True


def validate_input_fields(
    payload: dict[str, Any],
    fields: list[dict[str, Any]],
    *,
    path: str,
    fail: Fail,
) -> None:
    """Validate a reusable golden node input against its InputDefinition."""

    available = {cast(str, field["field_key"]): field for field in fields}
    required = {key for key, field in available.items() if cast(bool, field["required"])}
    if not required.issubset(payload) or not set(payload).issubset(available):
        fail("GOLDEN_NODE_INPUT_INVALID", f"{path} fields differ from InputDefinition")
    for key, value in payload.items():
        field = available[key]
        if value is None:
            if key in required:
                fail("GOLDEN_NODE_INPUT_INVALID", f"{path}.{key} is required")
            continue
        if not _input_type_matches(value, field):
            fail("GOLDEN_NODE_INPUT_INVALID", f"{path}.{key} has an invalid type")
        validation = cast(dict[str, Any], field.get("validation", {}))
        if isinstance(value, int | float) and not isinstance(value, bool):
            if "minimum" in validation and value < validation["minimum"]:
                fail("GOLDEN_NODE_INPUT_INVALID", f"{path}.{key} is below minimum")
            if "maximum" in validation and value > validation["maximum"]:
                fail("GOLDEN_NODE_INPUT_INVALID", f"{path}.{key} exceeds maximum")
        if isinstance(value, str) and len(value) > cast(
            int, validation.get("max_length", len(value))
        ):
            fail("GOLDEN_NODE_INPUT_INVALID", f"{path}.{key} exceeds max_length")


def validate_content_fields(
    payload: dict[str, Any],
    fields: list[dict[str, Any]],
    *,
    path: str,
    fail: Fail,
) -> None:
    expected = {cast(str, field["field_key"]) for field in fields}
    if set(payload) != expected:
        fail("GOLDEN_CONTENT_SHAPE_INVALID", f"{path} fields differ from ContentDefinition")
    for field in fields:
        key = cast(str, field["field_key"])
        value = payload[key]
        if field["required"] and value is None:
            fail("GOLDEN_CONTENT_SHAPE_INVALID", f"{path}.{key} is required")
        if value is None:
            continue
        if not _type_matches(value, field):
            fail("GOLDEN_CONTENT_SHAPE_INVALID", f"{path}.{key} has an invalid type")
        if isinstance(value, list) and len(value) < cast(int, field.get("min_items", 0)):
            fail("GOLDEN_CONTENT_SHAPE_INVALID", f"{path}.{key} has too few items")
        if isinstance(value, list) and "max_items" in field:
            if len(value) > cast(int, field["max_items"]):
                fail("GOLDEN_CONTENT_SHAPE_INVALID", f"{path}.{key} has too many items")
        children = cast(list[dict[str, Any]], field.get("children", []))
        if not children:
            continue
        records = value if isinstance(value, list) else [value]
        if not all(isinstance(record, dict) for record in records):
            fail("GOLDEN_CONTENT_SHAPE_INVALID", f"{path}.{key} must contain objects")
        for index, record in enumerate(cast(list[dict[str, Any]], records)):
            validate_content_fields(
                record,
                children,
                path=f"{path}.{key}[{index}]",
                fail=fail,
            )
