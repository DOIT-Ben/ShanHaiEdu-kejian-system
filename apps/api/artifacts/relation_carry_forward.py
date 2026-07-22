"""Carry unchanged keyed dependency edges to an approved replacement version."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.domain import (
    ArtifactImpactScope,
    ArtifactInvariantError,
    ArtifactRelationType,
    StaleImpactSelection,
)
from apps.api.artifacts.models import ArtifactRelation, ArtifactVersion
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7


def stale_reason_code(replacement_version_id: UUID | None) -> str:
    return (
        "UPSTREAM_APPROVAL_REVOKED"
        if replacement_version_id is None
        else "UPSTREAM_APPROVED_VERSION_CHANGED"
    )


def build_stale_reason(
    previous_version_id: UUID,
    replacement_version_id: UUID | None,
    relations: Sequence[tuple[ArtifactRelation, ArtifactImpactScope]],
    reason_code: str,
) -> dict[str, Any]:
    bindings = [
        {
            "relation_type": relation.relation_type,
            "binding_key": relation.binding_key,
            "impact_scope": effective_scope.as_dict(),
        }
        for relation, effective_scope in relations
    ]
    bindings.sort(
        key=lambda item: (
            item["relation_type"],
            item["binding_key"],
            json.dumps(item["impact_scope"], sort_keys=True),
        )
    )
    return {
        "reason_code": reason_code,
        "replaced_upstream_version_id": str(previous_version_id),
        "replacement_version_id": (
            str(replacement_version_id) if replacement_version_id is not None else None
        ),
        "bindings": bindings,
    }


def active_relations_with_carry(
    session: Session,
    actor: ActorContext,
    source_artifact_id: UUID,
    relations: list[ArtifactRelation],
    current_version_ids: set[UUID | None],
    replacement_version_id: UUID | None,
    selection: StaleImpactSelection | None,
) -> list[ArtifactRelation]:
    active = [
        relation
        for relation in relations
        if relation.to_artifact_version_id in current_version_ids
        and relation.relation_type != ArtifactRelationType.SUPERSEDES.value
    ]
    if replacement_version_id is not None and selection is not None:
        _require_replacement(session, actor, source_artifact_id, replacement_version_id)
        _carry(session, actor, active, replacement_version_id, selection)
    return active


def _carry(
    session: Session,
    actor: ActorContext,
    relations: list[ArtifactRelation],
    replacement_version_id: UUID,
    selection: StaleImpactSelection,
) -> None:
    for relation in relations:
        scope = ArtifactImpactScope.from_mapping(relation.impact_scope_json)
        if scope.mode != "keyed":
            continue
        retained = _retained_scope(selection, scope)
        if retained is None:
            continue
        existing = session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.organization_id == actor.organization_id,
                ArtifactRelation.from_artifact_version_id == replacement_version_id,
                ArtifactRelation.to_artifact_version_id == relation.to_artifact_version_id,
                ArtifactRelation.relation_type == relation.relation_type,
                ArtifactRelation.binding_key == relation.binding_key,
            )
        )
        if existing is not None:
            if existing.impact_scope_json != retained.as_dict():
                raise _conflict("The carried relation already exists with another scope.")
            continue
        session.add(
            ArtifactRelation(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                from_artifact_version_id=replacement_version_id,
                to_artifact_version_id=relation.to_artifact_version_id,
                relation_type=relation.relation_type,
                binding_key=relation.binding_key,
                impact_scope_json=retained.as_dict(),
                created_by=actor.principal_id,
            )
        )
    session.flush()


def _require_replacement(
    session: Session,
    actor: ActorContext,
    source_artifact_id: UUID,
    replacement_version_id: UUID,
) -> None:
    replacement_artifact_id = session.scalar(
        select(ArtifactVersion.artifact_id).where(
            ArtifactVersion.id == replacement_version_id,
            ArtifactVersion.organization_id == actor.organization_id,
        )
    )
    if replacement_artifact_id != source_artifact_id:
        raise ApiError(
            status_code=409,
            code="ARTIFACT_REPLACEMENT_SCOPE_INVALID",
            message="The replacement version does not belong to the replaced artifact.",
        )


def _retained_scope(
    selection: StaleImpactSelection,
    scope: ArtifactImpactScope,
) -> ArtifactImpactScope | None:
    try:
        return selection.matches(scope)
    except ArtifactInvariantError as exc:
        raise ApiError(
            status_code=409,
            code="ARTIFACT_IMPACT_SELECTION_INVALID",
            message=str(exc),
        ) from exc


def _conflict(message: str) -> ApiError:
    return ApiError(
        status_code=409,
        code="ARTIFACT_RELATION_SCOPE_CONFLICT",
        message=message,
    )
