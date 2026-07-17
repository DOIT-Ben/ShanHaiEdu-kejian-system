"""Pure artifact invariants shared by the application and tests."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Any
from uuid import UUID


class ArtifactInvariantError(ValueError):
    """Raised when an artifact graph or state invariant is violated."""


class ApprovalAction(StrEnum):
    SUBMIT = "submit"
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REVOKE = "revoke"
    ACCEPT_STALE = "accept_stale"


def canonical_content_hash(content: Mapping[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
