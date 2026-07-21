"""Stable identity addressing for server-owned repeatable item provisioning."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast

from apps.api.content_runtime.authoring_policy import AuthoringViolation, FieldPolicy

if TYPE_CHECKING:
    from apps.api.content_runtime.authoring_policy import AuthoringPolicy


def repeatable_item_identity(
    policy: AuthoringPolicy,
    field_path: tuple[str, ...],
    item: Mapping[str, Any],
) -> str:
    field = _field_at(policy.fields, field_path)
    if not field.repeatable or not field.locked_descendants:
        raise AuthoringViolation(field_path, "repeatable field has no stable identity")
    return locked_item_identity(item, field.locked_descendants, field_path)


def provision_repeatable_item(
    policy: AuthoringPolicy,
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    field_path: tuple[str, ...],
    parent_identities: tuple[str, ...],
    item: Mapping[str, Any],
) -> dict[str, Any]:
    policy.validate_update(baseline, candidate)
    result = deepcopy(dict(candidate))
    field, target = _repeatable_target(policy, result, field_path, parent_identities)
    if not field.editable or not field.locked_descendants:
        raise AuthoringViolation(field_path, "field does not allow identity provisioning")
    unknown = set(item).difference(child.field_key for child in field.children)
    if unknown:
        raise AuthoringViolation(field_path, "provisioned item contains unknown fields")
    identity = locked_item_identity(item, field.locked_descendants, field_path)
    existing = _index_items(target, field.locked_descendants, field_path)
    if identity in existing:
        raise AuthoringViolation(field_path, "repeatable locked identity must be unique")
    target.append(deepcopy(dict(item)))
    _validate_quantity(field, target, field_path)
    return result


def locked_item_identity(
    item: Mapping[str, Any],
    locked_paths: tuple[tuple[str, ...], ...],
    path: tuple[str, ...],
) -> str:
    values: list[tuple[tuple[str, ...], object]] = []
    for locked_path in locked_paths:
        value = _resolve_path(item, locked_path)
        if value is _MISSING:
            raise AuthoringViolation((*path, *locked_path), "locked identity is missing")
        values.append((locked_path, value))
    payload = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _repeatable_target(
    policy: AuthoringPolicy,
    content: dict[str, Any],
    field_path: tuple[str, ...],
    parent_identities: tuple[str, ...],
) -> tuple[FieldPolicy, list[object]]:
    if not field_path:
        raise AuthoringViolation(field_path, "authoring field path is empty")
    fields = policy.fields
    current: Mapping[str, Any] = content
    selector_index = 0
    walked: tuple[str, ...] = ()
    for index, key in enumerate(field_path):
        walked = (*walked, key)
        field = next((candidate for candidate in fields if candidate.field_key == key), None)
        if field is None or key not in current:
            raise AuthoringViolation(field_path, "authoring field path is unavailable")
        value = current[key]
        if field.repeatable:
            target = _require_list(value, walked)
            if index == len(field_path) - 1:
                if selector_index != len(parent_identities):
                    raise AuthoringViolation(field_path, "parent identity count is invalid")
                return field, target
            if selector_index >= len(parent_identities) or not field.locked_descendants:
                raise AuthoringViolation(walked, "nested repeatable parent identity is missing")
            indexed = _index_items(target, field.locked_descendants, walked)
            parent = indexed.get(parent_identities[selector_index])
            if parent is None:
                raise AuthoringViolation(walked, "nested repeatable parent is unavailable")
            current = parent
            selector_index += 1
        else:
            if not isinstance(value, Mapping):
                raise AuthoringViolation(walked, "authoring object path is unavailable")
            current = cast(Mapping[str, Any], value)
        fields = field.children
    raise AuthoringViolation(field_path, "authoring field path is not repeatable")


def _field_at(fields: tuple[FieldPolicy, ...], path: tuple[str, ...]) -> FieldPolicy:
    field: FieldPolicy | None = None
    for key in path:
        field = next((candidate for candidate in fields if candidate.field_key == key), None)
        if field is None:
            raise AuthoringViolation(path, "authoring field path is unknown")
        fields = field.children
    if field is None:
        raise AuthoringViolation(path, "authoring field path is empty")
    return field


def _index_items(
    items: Sequence[object],
    locked_paths: tuple[tuple[str, ...], ...],
    path: tuple[str, ...],
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for raw in items:
        if not isinstance(raw, Mapping):
            raise AuthoringViolation(path, "repeatable items must be objects")
        item = cast(Mapping[str, Any], raw)
        identity = locked_item_identity(item, locked_paths, path)
        if identity in indexed:
            raise AuthoringViolation(path, "repeatable locked identity must be unique")
        indexed[identity] = item
    return indexed


def _validate_quantity(
    field: FieldPolicy,
    items: Sequence[object],
    path: tuple[str, ...],
) -> None:
    if field.min_items is not None and len(items) < field.min_items:
        raise AuthoringViolation(path, "repeatable field is below its minimum size")
    if field.max_items is not None and len(items) > field.max_items:
        raise AuthoringViolation(path, "repeatable field exceeds its maximum size")


def _require_list(value: object, path: tuple[str, ...]) -> list[object]:
    if not isinstance(value, list):
        raise AuthoringViolation(path, "repeatable field must contain an array")
    return cast(list[object], value)


def _resolve_path(value: Mapping[str, Any], path: tuple[str, ...]) -> object:
    current: object = value
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return _MISSING
        current = cast(Mapping[str, object], current)[key]
    return current


_MISSING = object()
