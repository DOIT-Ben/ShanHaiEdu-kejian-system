"""Compile immutable content definition payloads into authoring policies."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast

from apps.api.content_runtime.authoring_policy import (
    AuthoringPolicy,
    AuthoringPolicyUnavailable,
    FieldPolicy,
)


def compile_authoring_policy(payload: object, *, checksum: str) -> AuthoringPolicy:
    if not isinstance(payload, Mapping):
        raise AuthoringPolicyUnavailable("published content definition is unavailable")
    payload_mapping = cast(Mapping[str, object], payload)
    if payload_mapping.get("kind") != "content_definition":
        raise AuthoringPolicyUnavailable("published content definition is unavailable")
    raw_spec = payload_mapping.get("spec")
    if not isinstance(raw_spec, Mapping):
        raise AuthoringPolicyUnavailable("published content definition has no policy spec")
    spec = cast(Mapping[str, object], raw_spec)
    definition_key = spec.get("definition_key")
    raw_fields = spec.get("fields")
    if not isinstance(definition_key, str) or not definition_key:
        raise AuthoringPolicyUnavailable("published content definition key is invalid")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise AuthoringPolicyUnavailable("published content definition fields are unavailable")
    fields = cast(list[object], raw_fields)
    if type(checksum) is not str or len(checksum) != 64:
        raise AuthoringPolicyUnavailable("published content definition checksum is invalid")
    try:
        compiled = tuple(_compile_field(field, ()) for field in fields)
    except (TypeError, ValueError) as exc:
        raise AuthoringPolicyUnavailable(
            "published content definition policy is incomplete"
        ) from exc
    _require_unique((field.field_key for field in compiled), ())
    return AuthoringPolicy(definition_key, checksum, compiled)


def _compile_field(raw: object, parent_path: tuple[str, ...]) -> FieldPolicy:
    if not isinstance(raw, Mapping):
        raise TypeError("field must be an object")
    mapping = cast(Mapping[str, object], raw)
    key = mapping.get("field_key")
    field_type = mapping.get("type")
    editable = mapping.get("editable")
    deletable = mapping.get("deletable")
    if (
        not isinstance(key, str)
        or not key
        or not isinstance(field_type, str)
        or type(editable) is not bool
        or type(deletable) is not bool
    ):
        raise ValueError("field authoring flags are incomplete")
    children_raw = mapping.get("children", [])
    if not isinstance(children_raw, list):
        raise TypeError("field children must be an array")
    children = tuple(
        _compile_field(child, (*parent_path, key)) for child in cast(list[object], children_raw)
    )
    _require_unique((child.field_key for child in children), (*parent_path, key))
    repeatable = mapping.get("repeatable", field_type == "repeatable")
    if type(repeatable) is not bool:
        raise TypeError("repeatable flag must be boolean")
    min_items = mapping.get("min_items")
    max_items = mapping.get("max_items")
    if min_items is not None and (type(min_items) is not int or min_items < 0):
        raise TypeError("min_items must be a non-negative integer")
    if max_items is not None and (type(max_items) is not int or max_items < 1):
        raise TypeError("max_items must be a positive integer")
    if min_items is not None and max_items is not None and min_items > max_items:
        raise ValueError("repeatable item bounds are invalid")
    return FieldPolicy(
        key,
        field_type,
        editable,
        deletable,
        repeatable,
        min_items,
        max_items,
        children,
    )


def _require_unique(values: Iterable[str], path: tuple[str, ...]) -> None:
    values = tuple(values)
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate field key at {'.'.join(path)}")
