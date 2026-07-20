"""Immutable JSON value helpers shared by runtime-boundary contracts."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping, Sequence
from types import MappingProxyType
from typing import Any, Self, cast
from uuid import UUID

from apps.api.artifacts.domain import ArtifactInvariantError

_CONTENT_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class FrozenJsonDict(Mapping[str, Any]):
    """A read-only JSON mapping with no mutable ``dict`` base-class escape."""

    __slots__ = ("__values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        self.__values = MappingProxyType(dict(values))

    def __getitem__(self, key: str) -> Any:
        return self.__values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.__values)

    def __len__(self) -> int:
        return len(self.__values)

    def __repr__(self) -> str:
        return f"FrozenJsonDict({dict(self.__values)!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return False
        return dict(self.items()) == dict(cast(Mapping[object, object], other).items())

    def __copy__(self) -> Self:
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> Self:
        return self


def freeze_json_value(value: object) -> Any:
    """Deep-freeze a finite JSON value for immutable runtime DTOs."""

    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        entries = cast(Mapping[object, object], value)
        for key, child in entries.items():
            if type(key) is not str:
                raise ArtifactInvariantError("JSON mapping keys must be strings")
            frozen[key] = freeze_json_value(child)
        return FrozenJsonDict(frozen)
    if isinstance(value, (list, tuple)):
        values = cast(Sequence[object], value)
        return tuple(freeze_json_value(child) for child in values)
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ArtifactInvariantError("JSON values must be finite and JSON-compatible")


def require_uuid(value: object, message: str) -> None:
    if not isinstance(value, UUID):
        raise ArtifactInvariantError(message)


def require_uuid_fields(*fields: tuple[object, str]) -> None:
    for value, message in fields:
        require_uuid(value, message)


def require_text(value: object, message: str, maximum: int) -> None:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ArtifactInvariantError(message)


def require_content_hash(value: object, message: str) -> None:
    if type(value) is not str or _CONTENT_HASH_PATTERN.fullmatch(value) is None:
        raise ArtifactInvariantError(message)
