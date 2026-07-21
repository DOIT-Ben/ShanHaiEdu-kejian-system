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
    min_items: int | None = None
    max_items: int | None = None
    children: tuple[FieldPolicy, ...] = ()

    @property
    def locked_descendants(self) -> tuple[tuple[str, ...], ...]:
        paths: list[tuple[str, ...]] = []
        for child in self.children:
            if not child.editable:
                paths.append((child.field_key,))
            elif not child.repeatable:
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
        parent_identities: tuple[str, ...] = (),
        item: Mapping[str, Any],
    ) -> dict[str, Any]:
        from apps.api.content_runtime.authoring_policy_provision import (
            provision_repeatable_item,
        )

        return provision_repeatable_item(
            self,
            baseline,
            candidate,
            field_path=field_path,
            parent_identities=parent_identities,
            item=item,
        )

    def repeatable_item_identity(
        self,
        field_path: tuple[str, ...],
        item: Mapping[str, Any],
    ) -> str:
        from apps.api.content_runtime.authoring_policy_provision import (
            repeatable_item_identity,
        )

        return repeatable_item_identity(self, field_path, item)

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
            self._validate_quantity(field, items, path)
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
            return
        if not old_present:
            if field.repeatable:
                items = _require_sequence(candidate[key], path)
                self._validate_quantity(field, items, path)
                for item in items:
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
        self._validate_quantity(field, new_items, path)
        locked_paths = field.locked_descendants
        if not locked_paths:
            return

        old_by_identity = self._index_items(old_items, locked_paths, path)
        new_by_identity = self._index_items(new_items, locked_paths, path)
        for identity, item in new_by_identity.items():
            old_item = old_by_identity.get(identity)
            if old_item is None:
                raise AuthoringViolation(
                    path,
                    "new repeatable items with locked identity require server provisioning",
                )
            self._validate_item_update(field, old_item, item, path)

    @staticmethod
    def _validate_quantity(
        field: FieldPolicy,
        items: Sequence[object],
        path: tuple[str, ...],
    ) -> None:
        if field.min_items is not None and len(items) < field.min_items:
            raise AuthoringViolation(path, "repeatable field is below its minimum size")
        if field.max_items is not None and len(items) > field.max_items:
            raise AuthoringViolation(path, "repeatable field exceeds its maximum size")

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
            from apps.api.content_runtime.authoring_policy_provision import (
                locked_item_identity,
            )

            identity = locked_item_identity(mapping, locked_paths, path)
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


def _json_equal(left: Any, right: Any) -> bool:
    return _canonical(left) == _canonical(right)


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_MISSING = object()
