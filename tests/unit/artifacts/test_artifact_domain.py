from __future__ import annotations

from uuid import UUID

import pytest

from apps.api.artifacts.domain import (
    ArtifactInvariantError,
    canonical_content_hash,
    ensure_relation_is_acyclic,
)


def test_content_hash_is_stable_for_equivalent_json() -> None:
    left = {"title": "Fractions", "sections": [{"position": 1, "text": "One half"}]}
    right = {"sections": [{"text": "One half", "position": 1}], "title": "Fractions"}

    assert canonical_content_hash(left) == canonical_content_hash(right)
    assert len(canonical_content_hash(left)) == 64


def test_relation_cycle_is_rejected() -> None:
    first = UUID("01990000-0000-7000-8000-000000000001")
    second = UUID("01990000-0000-7000-8000-000000000002")
    third = UUID("01990000-0000-7000-8000-000000000003")

    with pytest.raises(ArtifactInvariantError, match="cycle"):
        ensure_relation_is_acyclic(
            existing_edges=((first, second), (second, third)),
            from_artifact_id=third,
            to_artifact_id=first,
        )
