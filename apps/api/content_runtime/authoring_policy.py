"""Immutable ContentDefinition authoring policy compilation and enforcement."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast


class AuthoringPolicyUnavailable(ValueError):
    """The published definition does not contain a complete authoring policy."""


class AuthoringViolation(ValueError):
    """A user mutation changes a value outside the published authoring policy."""

    def __init__(self, paths: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.paths = paths
        self.message = message


@dataclass(frozen=True, slots=True)
class FieldPolicy:
    field_key: str
    field_type: str
    editable: bool
    deletable: bool
    repeatable: bool
    children: tuple[FieldPolicy, ...] = ()

    @property
    def locked_descendants(self) -> tuple[tuple[str, ...], ...]:
        paths: list[tuple[str, ...]] = []
        for child in self.children:
            if not child.editable:
                paths.append((child.field_key,))
            for nested in child.locked_descendants:
                paths.append((child.field_key, *nested))
        return tuple(paths)


@dataclass(frozen=True, slots=True)
class AuthoringPolicy:
    definition_key: str
    checksum: str
    fields: tuple[FieldPolicy, ...]

    def validate_create(self, content: Mapping[str, Any]) -> None:
        if not isinstance(content, Mapping):
            raise AuthoringViolation((), "artifact content must be an object")
        for field in self.fields:
            self._validate_create_field(field, cast(Mapping[str, Any], content), ())

    def validate_update(
        self,
        baseline: Mapping[str, Any],
        candidate: Mapping[str, Any],
    ) -> None:
        if not isinstance(baseline, Mapping) or not isinstance(candidate, Mapping):
            raise AuthoringViolation((), "artifact content must be an object")
        for field in self.fields:
            self._validate_update_field(
                field,
                cast(Mapping[str, Any], baseline),
                cast(Mapping[str, Any], candidate),
                (),
            )

    def _validate_create_field(
        self,
        field: FieldPolicy,
        content: Mapping[str, Any],
        parent_path: tuple[str, ...],
    ) -> None:
        key = field.field_key
        path = (*parent_path, key)
        if key not in content:
            return
        value = content[key]
        if not field.editable:
            raise AuthoringViolation(path, "locked field cannot be supplied by this writer")
        if field.repeatable:
            items = _require_sequence(value, path)
            for item in items:
                self._validate_new_item(field, item, path)
            return
        self._validate_create_children(field, value, path)

    def _validate_create_children(
        self,
        field: FieldPolicy,
        value: object,
        path: tuple[str, ...],
    ) -> None:
        if not field.children:
            return
        if not isinstance(value, Mapping):
            raise AuthoringViolation(path, "object field must contain an object value")
        mapping = cast(Mapping[str, Any], value)
        for child in field.children:
            self._validate_create_field(child, mapping, path)

    def _validate_new_item(
        self,
        field: FieldPolicy,
        item: object,
        path: tuple[str, ...],
    ) -> None:
        if not isinstance(item, Mapping):
            raise AuthoringViolation(path, "repeatable items must be objects")
        mapping = cast(Mapping[str, Any], item)
        if field.locked_descendants:
            for locked_path in field.locked_descendants:
                if _has_path(mapping, locked_path):
                    raise AuthoringViolation(
                        (*path, *locked_path),
                        "new repeatable items with locked identity require server provisioning",
                    )
        for child in field.children:
            self._validate_create_field(child, mapping, path)

    def _validate_update_field(
        self,
        field: FieldPolicy,
        baseline: Mapping[str, Any],
        candidate: Mapping[str, Any],
        parent_path: tuple[str, ...],
    ) -> None:
        key = field.field_key
        path = (*parent_path, key)
        old_present = key in baseline
        new_present = key in candidate
        if not old_present and not new_present:
            return
        if not field.editable:
            if old_present != new_present or (
                old_present and not _json_equal(baseline[key], candidate[key])
            ):
                raise AuthoringViolation(path, "locked field cannot be changed")
            return
        if old_present and not new_present:
            if not field.deletable:
                raise AuthoringViolation(path, "field is not deletable")
            return
        if not old_present:
            if field.repeatable:
                for item in _require_sequence(candidate[key], path):
                    self._validate_new_item(field, item, path)
            else:
                self._validate_create_children(field, candidate[key], path)
            return
        if field.repeatable:
            self._validate_repeatable_update(
                field,
                _require_sequence(baseline[key], path),
                _require_sequence(candidate[key], path),
                path,
            )
            return
        self._validate_update_children(field, baseline[key], candidate[key], path)

    def _validate_update_children(
        self,
        field: FieldPolicy,
        old_value: object,
        new_value: object,
        path: tuple[str, ...],
    ) -> None:
        if not field.children:
            return
        if not isinstance(old_value, Mapping) or not isinstance(new_value, Mapping):
            if not _json_equal(old_value, new_value):
                raise AuthoringViolation(path, "object field cannot change shape")
            return
        old_mapping = cast(Mapping[str, Any], old_value)
        new_mapping = cast(Mapping[str, Any], new_value)
        for child in field.children:
            self._validate_update_field(child, old_mapping, new_mapping, path)

    def _validate_repeatable_update(
        self,
        field: FieldPolicy,
        old_items: Sequence[object],
        new_items: Sequence[object],
        path: tuple[str, ...],
    ) -> None:
        locked_paths = field.locked_descendants
        if not locked_paths:
            if not field.deletable and len(new_items) < len(old_items):
                raise AuthoringViolation(path, "repeatable field is not deletable")
            for index, (old_item, new_item) in enumerate(zip(old_items, new_items, strict=False)):
                self._validate_item_update(field, old_item, new_item, (*path, str(index)))
            for item in new_items[len(old_items) :]:
                self._validate_new_item(field, item, path)
            return

        old_by_identity = self._index_items(old_items, locked_paths, path)
        new_by_identity = self._index_items(new_items, locked_paths, path)
        if not field.deletable and set(old_by_identity) != set(new_by_identity):
            raise AuthoringViolation(path, "repeatable field is not deletable")
        for identity, item in new_by_identity.items():
            old_item = old_by_identity.get(identity)
            if old_item is None:
                raise AuthoringViolation(
                    path,
                    "new repeatable items with locked identity require server provisioning",
                )
            self._validate_item_update(field, old_item, item, path)

    def _index_items(
        self,
        items: Sequence[object],
        locked_paths: tuple[tuple[str, ...], ...],
        path: tuple[str, ...],
    ) -> dict[str, Mapping[str, Any]]:
        indexed: dict[str, Mapping[str, Any]] = {}
        for item in items:
            if not isinstance(item, Mapping):
                raise AuthoringViolation(path, "repeatable items must be objects")
            mapping = cast(Mapping[str, Any], item)
            values: list[tuple[tuple[str, ...], object]] = []
            for locked_path in locked_paths:
                value = _resolve_path(mapping, locked_path)
                if value is _MISSING:
                    raise AuthoringViolation((*path, *locked_path), "locked identity is missing")
                values.append((locked_path, value))
            identity = _canonical(values)
            if identity in indexed:
                raise AuthoringViolation(path, "repeatable locked identity must be unique")
            indexed[identity] = mapping
        return indexed

    def _validate_item_update(
        self,
        field: FieldPolicy,
        old_item: object,
        new_item: object,
        path: tuple[str, ...],
    ) -> None:
        if not isinstance(old_item, Mapping) or not isinstance(new_item, Mapping):
            raise AuthoringViolation(path, "repeatable items must be objects")
        old_mapping = cast(Mapping[str, Any], old_item)
        new_mapping = cast(Mapping[str, Any], new_item)
        for child in field.children:
            self._validate_update_field(child, old_mapping, new_mapping, path)


def compile_authoring_policy(payload: Mapping[str, Any], *, checksum: str) -> AuthoringPolicy:
    if not isinstance(payload, Mapping) or payload.get("kind") != "content_definition":
        raise AuthoringPolicyUnavailable("published content definition is unavailable")
    spec = payload.get("spec")
    if not isinstance(spec, Mapping):
        raise AuthoringPolicyUnavailable("published content definition has no policy spec")
    definition_key = spec.get("definition_key")
    fields = spec.get("fields")
    if not isinstance(definition_key, str) or not definition_key:
        raise AuthoringPolicyUnavailable("published content definition key is invalid")
    if not isinstance(fields, list) or not fields:
        raise AuthoringPolicyUnavailable("published content definition fields are unavailable")
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
    key = raw.get("field_key")
    field_type = raw.get("type")
    editable = raw.get("editable")
    deletable = raw.get("deletable")
    if (
        type(key) is not str
        or not key
        or type(field_type) is not str
        or type(editable) is not bool
        or type(deletable) is not bool
    ):
        raise ValueError("field authoring flags are incomplete")
    children_raw = raw.get("children", [])
    if not isinstance(children_raw, list):
        raise TypeError("field children must be an array")
    children = tuple(_compile_field(child, (*parent_path, key)) for child in children_raw)
    _require_unique((child.field_key for child in children), (*parent_path, key))
    repeatable = raw.get("repeatable", field_type == "repeatable")
    if type(repeatable) is not bool:
        raise TypeError("repeatable flag must be boolean")
    return FieldPolicy(key, field_type, editable, deletable, repeatable, children)


def _require_unique(values: Sequence[str] | Any, path: tuple[str, ...]) -> None:
    values = tuple(values)
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate field key at {'.'.join(path)}")


def _require_sequence(value: object, path: tuple[str, ...]) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise AuthoringViolation(path, "repeatable field must contain an array")
    return value


def _resolve_path(value: Mapping[str, Any], path: tuple[str, ...]) -> object:
    current: object = value
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return _MISSING
        current = current[key]
    return current


def _has_path(value: Mapping[str, Any], path: tuple[str, ...]) -> bool:
    return _resolve_path(value, path) is not _MISSING


def _json_equal(left: object, right: object) -> bool:
    return _canonical(left) == _canonical(right)


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_MISSING = object()
