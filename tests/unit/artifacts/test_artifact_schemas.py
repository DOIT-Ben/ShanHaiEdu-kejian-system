from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from apps.api.artifacts.schemas import ArtifactStaleReasonRead, ReviewArtifactVersionRequest


def _reason(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "reason_code": "UPSTREAM_APPROVED_VERSION_CHANGED",
        "replaced_upstream_version_id": "01990000-0000-7000-8000-000000000001",
        "replacement_version_id": "01990000-0000-7000-8000-000000000002",
        "bindings": [
            {
                "relation_type": "derives_from",
                "binding_key": "lesson-scope",
                "impact_scope": {"mode": "all"},
            }
        ],
    }
    value.update(overrides)
    return value


def test_stale_reason_accepts_exact_replacement_shape() -> None:
    reason = ArtifactStaleReasonRead.model_validate(_reason())

    assert reason.replaced_upstream_version_id == UUID("01990000-0000-7000-8000-000000000001")


def test_stale_reason_accepts_sorted_keyed_scope() -> None:
    reason = ArtifactStaleReasonRead.model_validate(
        _reason(
            bindings=[
                {
                    "relation_type": "references",
                    "binding_key": "lesson-scope",
                    "impact_scope": {
                        "mode": "keyed",
                        "selector": "lesson_key",
                        "keys": ["LESSON-001", "LESSON-002"],
                    },
                }
            ]
        )
    )

    assert reason.bindings[0].impact_scope.keys == ["LESSON-001", "LESSON-002"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"extra": True},
        {"replacement_version_id": None},
        {
            "bindings": [
                {
                    "relation_type": "derives_from",
                    "binding_key": "lesson-scope",
                    "impact_scope": {
                        "mode": "keyed",
                        "selector": "lesson_unit_key",
                        "keys": ["LESSON-001"],
                    },
                }
            ]
        },
        {
            "bindings": [
                {
                    "relation_type": "derives_from",
                    "binding_key": "lesson-scope",
                    "impact_scope": {
                        "mode": "keyed",
                        "selector": "lesson_key",
                        "keys": ["LESSON-002", "LESSON-001"],
                    },
                }
            ]
        },
    ],
)
def test_stale_reason_rejects_extra_or_incompatible_shapes(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ArtifactStaleReasonRead.model_validate(_reason(**overrides))


def test_revoke_requires_null_replacement() -> None:
    with pytest.raises(ValidationError):
        ArtifactStaleReasonRead.model_validate(_reason(reason_code="UPSTREAM_APPROVAL_REVOKED"))

    reason = ArtifactStaleReasonRead.model_validate(
        _reason(
            reason_code="UPSTREAM_APPROVAL_REVOKED",
            replacement_version_id=None,
        )
    )
    assert reason.replacement_version_id is None


@pytest.mark.parametrize("field", ["report_id", "quality_evidence"])
def test_review_request_rejects_client_quality_evidence(field: str) -> None:
    with pytest.raises(ValidationError):
        ReviewArtifactVersionRequest.model_validate(
            {"action": "approve", field: "forged" if field == "report_id" else {}}
        )
