"""Pure artifact invariants shared by the application and tests."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, cast
from uuid import UUID


class ArtifactInvariantError(ValueError):
    """Raised when an artifact graph or state invariant is violated."""


class ApprovalAction(StrEnum):
    SUBMIT = "submit"
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REVOKE = "revoke"
    ACCEPT_STALE = "accept_stale"


class ArtifactRelationType(StrEnum):
    DERIVES_FROM = "derives_from"
    REFERENCES = "references"
    CONSTRAINS = "constrains"
    SUPERSEDES = "supersedes"

    @property
    def participates_in_dag(self) -> bool:
        return self is not ArtifactRelationType.SUPERSEDES

    @property
    def propagates_stale(self) -> bool:
        return self is not ArtifactRelationType.SUPERSEDES


class ImpactSelector(StrEnum):
    LESSON_KEY = "lesson_key"


@dataclass(frozen=True, slots=True)
class ArtifactImpactScope:
    mode: Literal["all", "keyed"]
    selector: ImpactSelector | None = None
    keys: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: object) -> ArtifactImpactScope:
        if not isinstance(value, Mapping):
            raise ArtifactInvariantError("impact_scope must be an object")
        value = cast(Mapping[str, Any], value)
        if set(value) == {"mode"} and value.get("mode") == "all":
            return cls(mode="all")
        if set(value) != {"mode", "selector", "keys"}:
            raise ArtifactInvariantError("impact_scope has an unsupported shape")
        if value.get("mode") != "keyed":
            raise ArtifactInvariantError("impact_scope mode is invalid")
        try:
            selector = ImpactSelector(value["selector"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ArtifactInvariantError("impact_scope selector is invalid") from exc
        raw_keys = value.get("keys")
        if not isinstance(raw_keys, (list, tuple)) or not raw_keys:
            raise ArtifactInvariantError("impact_scope keys must be non-empty")
        raw_keys = cast(list[Any] | tuple[Any, ...], raw_keys)
        if any(not isinstance(key, str) or not key.strip() for key in raw_keys):
            raise ArtifactInvariantError("impact_scope keys must be non-empty strings")
        keys = tuple(raw_keys)
        if len(set(keys)) != len(keys) or list(keys) != sorted(keys):
            raise ArtifactInvariantError("impact_scope keys must be unique and sorted")
        return cls(mode="keyed", selector=selector, keys=keys)

    def as_dict(self) -> dict[str, Any]:
        if self.mode == "all":
            return {"mode": "all"}
        return {
            "mode": "keyed",
            "selector": self.selector.value if self.selector is not None else None,
            "keys": list(self.keys),
        }


@dataclass(frozen=True, slots=True)
class StaleImpactDimension:
    selector: ImpactSelector
    changed_keys: tuple[str, ...] = ()
    archived_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        changed = tuple(self.changed_keys)
        archived = tuple(self.archived_keys)
        object.__setattr__(self, "changed_keys", changed)
        object.__setattr__(self, "archived_keys", archived)
        if type(self.selector) is not ImpactSelector:
            raise ArtifactInvariantError("stale impact selector is invalid")
        for values in (changed, archived):
            if any(type(key) is not str or not key.strip() for key in values):
                raise ArtifactInvariantError("stale impact keys must be non-empty")
            if len(set(values)) != len(values) or list(values) != sorted(values):
                raise ArtifactInvariantError("stale impact keys must be unique and sorted")
        if set(changed) & set(archived):
            raise ArtifactInvariantError("changed and archived keys must not overlap")

    @property
    def affected_keys(self) -> frozenset[str]:
        return frozenset((*self.changed_keys, *self.archived_keys))


@dataclass(frozen=True, slots=True)
class StaleImpactSelection:
    mode: Literal["all", "exact"]
    dimensions: tuple[StaleImpactDimension, ...] = ()

    def __post_init__(self) -> None:
        dimensions = tuple(self.dimensions)
        object.__setattr__(self, "dimensions", dimensions)
        if self.mode not in {"all", "exact"}:
            raise ArtifactInvariantError("stale impact selection mode is invalid")
        if self.mode == "all" and dimensions:
            raise ArtifactInvariantError("all stale impact selection cannot have dimensions")
        if any(type(item) is not StaleImpactDimension for item in dimensions):
            raise ArtifactInvariantError("stale impact selection dimensions are invalid")

    @classmethod
    def all(cls) -> StaleImpactSelection:
        return cls(mode="all")

    @classmethod
    def exact(cls, dimensions: Iterable[StaleImpactDimension]) -> StaleImpactSelection:
        values = tuple(dimensions)
        selectors = [dimension.selector for dimension in values]
        if len(set(selectors)) != len(selectors):
            raise ArtifactInvariantError("stale impact selectors must be unique")
        return cls(mode="exact", dimensions=values)

    def matches(self, scope: ArtifactImpactScope) -> ArtifactImpactScope | None:
        if self.mode == "all" or scope.mode == "all":
            return scope
        assert scope.selector is not None
        dimension = next(
            (item for item in self.dimensions if item.selector is scope.selector),
            None,
        )
        if dimension is None:
            raise ArtifactInvariantError("stale impact selection is missing a selector")
        affected = sorted(set(scope.keys) & dimension.affected_keys)
        if not affected:
            return None
        return ArtifactImpactScope(
            mode="keyed",
            selector=scope.selector,
            keys=tuple(affected),
        )


def canonical_content_hash(content: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        _plain_json_value(content),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _plain_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: _plain_json_value(child)
            for key, child in cast(Mapping[str, object], value).items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain_json_value(child) for child in cast(Sequence[object], value)]
    return value


def ensure_relation_is_acyclic(
    *,
    existing_edges: Iterable[tuple[UUID, UUID]],
    from_artifact_id: UUID,
    to_artifact_id: UUID,
) -> None:
    if from_artifact_id == to_artifact_id:
        raise ArtifactInvariantError("artifact relation would create a cycle")
    outgoing: dict[UUID, list[UUID]] = defaultdict(list)
    for source, target in existing_edges:
        outgoing[source].append(target)
    pending = [to_artifact_id]
    visited: set[UUID] = set()
    while pending:
        current = pending.pop()
        if current == from_artifact_id:
            raise ArtifactInvariantError("artifact relation would create a cycle")
        if current in visited:
            continue
        visited.add(current)
        pending.extend(outgoing[current])
