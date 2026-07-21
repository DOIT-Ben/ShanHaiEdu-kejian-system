"""Immutable ContentDefinition authoring policy compilation and enforcement."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
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
        for field in self.fields:
            self._validate_create_field(field, content, ())

    def validate_update(
        self,
        baseline: Mapping[str, Any],
        candidate: Mapping[str, Any],
    ) -> None:
        for field in self.fields:
            self._validate_update_field(
                field,
                baseline,
                candidate,
                (),
            )

    def provision_repeatable_item(
        self,
        baseline: Mapping[str, Any],
        candidate: Mapping[str, Any],
        *,
        field_path: tuple[str, ...],
        item: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Append one server-owned item after validating all existing user changes."""

        self.validate_update(baseline, candidate)
        field = self._field_at(field_path)
        if not field.repeatable or not field.editable:
            raise AuthoringViolation(field_path, "field does not allow item provisioning")
        result = deepcopy(dict(candidate))
        target = _resolve_mutable_path(result, field_path)
        if not isinstance(target, list):
            raise AuthoringViolation(field_path, "repeatable field must contain an array")
        target_items = cast(list[object], target)
        locked_paths = field.locked_descendants
        if locked_paths:
            existing = self._index_items(target_items, locked_paths, field_path)
            values: list[tuple[tuple[str, ...], object]] = []
            for locked_path in locked_paths:
                value = _resolve_path(item, locked_path)
                if value is _MISSING:
                    raise AuthoringViolation(
                        (*field_path, *locked_path),
                        "provisioned item locked identity is missing",
                    )
                values.append((locked_path, value))
            if _canonical(values) in existing:
                raise AuthoringViolation(
                    field_path,
                    "repeatable locked identity must be unique",
                )
        target_items.append(deepcopy(dict(item)))
        return result

    def _field_at(self, path: tuple[str, ...]) -> FieldPolicy:
        if not path:
            raise AuthoringViolation(path, "authoring field path is empty")
        fields = self.fields
        field: FieldPolicy | None = None
        for part in path:
            field = next((item for item in fields if item.field_key == part), None)
            if field is None:
                raise AuthoringViolation(path, "authoring field path is unknown")
            fields = field.children
        assert field is not None
        return field

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
    return FieldPolicy(
        key,
        field_type,
        editable,
        deletable,
        repeatable,
        children,
    )


def _require_unique(values: Iterable[str], path: tuple[str, ...]) -> None:
    values = tuple(values)
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate field key at {'.'.join(path)}")


def _require_sequence(value: object, path: tuple[str, ...]) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise AuthoringViolation(path, "repeatable field must contain an array")
    return cast(Sequence[object], value)


def _resolve_path(value: Mapping[str, Any], path: tuple[str, ...]) -> object:
    current: object = value
    for key in path:
        if not isinstance(current, Mapping):
            return _MISSING
        mapping = cast(Mapping[str, object], current)
        if key not in mapping:
            return _MISSING
        current = mapping[key]
    return current


def _has_path(value: Mapping[str, Any], path: tuple[str, ...]) -> bool:
    return _resolve_path(value, path) is not _MISSING


def _resolve_mutable_path(value: dict[str, Any], path: tuple[str, ...]) -> object:
    current: object = value
    for key in path:
        if not isinstance(current, dict):
            return _MISSING
        mapping = cast(dict[str, object], current)
        if key not in mapping:
            return _MISSING
        current = mapping[key]
    return current


def _json_equal(left: Any, right: Any) -> bool:
    return _canonical(left) == _canonical(right)


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_MISSING = object()
