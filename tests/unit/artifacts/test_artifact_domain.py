from __future__ import annotations

from uuid import UUID

import pytest

from apps.api.artifacts.domain import (
    ArtifactImpactScope,
    ArtifactInvariantError,
    ArtifactRelationType,
    ImpactSelector,
    StaleImpactDimension,
    StaleImpactSelection,
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


@pytest.mark.parametrize(
    "scope",
    [
        {"mode": "all"},
        {"mode": "keyed", "selector": "lesson_key", "keys": ["LESSON-001"]},
    ],
)
def test_impact_scope_accepts_only_approved_shapes(scope: dict[str, object]) -> None:
    parsed = ArtifactImpactScope.from_mapping(scope)

    assert parsed.as_dict() == scope


@pytest.mark.parametrize(
    "scope",
    [
        {},
        {"mode": "all", "extra": True},
        {"mode": "keyed", "selector": "lesson_unit_key", "keys": ["LESSON-001"]},
        {"mode": "keyed", "selector": "lesson_key", "keys": []},
        {"mode": "keyed", "selector": "lesson_key", "keys": ["LESSON-002", "LESSON-001"]},
        {"mode": "keyed", "selector": "lesson_key", "keys": ["LESSON-001", "LESSON-001"]},
    ],
)
def test_impact_scope_rejects_unknown_or_noncanonical_shapes(
    scope: dict[str, object],
) -> None:
    with pytest.raises(ArtifactInvariantError):
        ArtifactImpactScope.from_mapping(scope)


def test_stale_selection_intersects_keyed_scope_and_preserves_all_scope() -> None:
    selection = StaleImpactSelection.exact(
        [
            StaleImpactDimension(
                selector=ImpactSelector.LESSON_KEY,
                changed_keys=("LESSON-001",),
                archived_keys=("LESSON-003",),
            )
        ]
    )

    assert selection.matches(
        ArtifactImpactScope(
            mode="keyed",
            selector=ImpactSelector.LESSON_KEY,
            keys=("LESSON-001", "LESSON-002"),
        )
    ) == ArtifactImpactScope(
        mode="keyed", selector=ImpactSelector.LESSON_KEY, keys=("LESSON-001",)
    )
    assert selection.matches(ArtifactImpactScope(mode="all")) == ArtifactImpactScope(mode="all")
    assert (
        selection.matches(
            ArtifactImpactScope(
                mode="keyed", selector=ImpactSelector.LESSON_KEY, keys=("LESSON-002",)
            )
        )
        is None
    )


def test_relation_type_policy_excludes_supersedes_from_stale_graph() -> None:
    assert ArtifactRelationType.DERIVES_FROM.participates_in_dag is True
    assert ArtifactRelationType.SUPERSEDES.participates_in_dag is False
    assert ArtifactRelationType.SUPERSEDES.propagates_stale is False
