"""Prompt-snapshot facts required by lesson-division quality validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.prompt_runtime.models import ContextSnapshot


@dataclass(frozen=True, slots=True)
class MaterialEvidenceSnapshot:
    project_id: UUID
    node_run_id: UUID
    source_material_id: UUID
    material_parse_version_id: UUID


@dataclass(frozen=True, slots=True)
class ApprovedMaterialScopeSnapshot:
    project_id: UUID
    node_run_id: UUID
    artifact_version_id: UUID


class LessonContextSnapshotReader:
    def __init__(self, session: Session, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    def material_evidence(self, context_snapshot_id: UUID) -> MaterialEvidenceSnapshot:
        context = self._session.get(ContextSnapshot, context_snapshot_id)
        if context is None or context.organization_id != self._organization_id:
            raise self._invalid("The frozen lesson-division context is unavailable.")
        bindings = context.bindings_json.get("bindings")
        if not isinstance(bindings, Sequence):
            raise self._invalid("The frozen lesson-division context is invalid.")
        items: list[Mapping[str, Any]] = []
        for raw in cast(Sequence[object], bindings):
            if not isinstance(raw, Mapping):
                continue
            binding = cast(Mapping[str, Any], raw)
            if binding.get("source") != "material.approved_parse":
                continue
            raw_items = binding.get("items")
            if isinstance(raw_items, Sequence):
                items.extend(
                    cast(Mapping[str, Any], item)
                    for item in cast(Sequence[object], raw_items)
                    if isinstance(item, Mapping)
                )
        if len(items) != 1:
            raise self._invalid("Exactly one formal material evidence snapshot is required.")
        return MaterialEvidenceSnapshot(
            project_id=context.project_id,
            node_run_id=context.node_run_id,
            source_material_id=_uuid_value(items[0].get("source_id")),
            material_parse_version_id=_uuid_value(items[0].get("source_version_id")),
        )

    def approved_material_scope(
        self,
        context_snapshot_id: UUID,
    ) -> ApprovedMaterialScopeSnapshot:
        context = self._require_context(context_snapshot_id)
        items = self._items_for_source(context, "material_scope.approved_version")
        if len(items) != 1:
            raise self._invalid("Exactly one approved material-scope snapshot is required.")
        return ApprovedMaterialScopeSnapshot(
            project_id=context.project_id,
            node_run_id=context.node_run_id,
            artifact_version_id=_uuid_value(items[0].get("source_version_id")),
        )

    def _require_context(self, context_snapshot_id: UUID) -> ContextSnapshot:
        context = self._session.get(ContextSnapshot, context_snapshot_id)
        if context is None or context.organization_id != self._organization_id:
            raise self._invalid("The frozen lesson-division context is unavailable.")
        return context

    def _items_for_source(
        self,
        context: ContextSnapshot,
        source: str,
    ) -> list[Mapping[str, Any]]:
        bindings = context.bindings_json.get("bindings")
        if not isinstance(bindings, Sequence):
            raise self._invalid("The frozen lesson-division context is invalid.")
        items: list[Mapping[str, Any]] = []
        for raw in cast(Sequence[object], bindings):
            if not isinstance(raw, Mapping):
                continue
            binding = cast(Mapping[str, Any], raw)
            if binding.get("source") != source:
                continue
            raw_items = binding.get("items")
            if isinstance(raw_items, Sequence):
                items.extend(
                    cast(Mapping[str, Any], item)
                    for item in cast(Sequence[object], raw_items)
                    if isinstance(item, Mapping)
                )
        return items

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(
            status_code=409,
            code="LESSON_DIVISION_RUNTIME_INVALID",
            message=message,
        )


def _uuid_value(value: object) -> UUID:
    if not isinstance(value, str):
        raise ApiError(
            status_code=409,
            code="LESSON_DIVISION_RUNTIME_INVALID",
            message="The frozen material identity is invalid.",
        )
    try:
        return UUID(value)
    except ValueError as exc:
        raise ApiError(
            status_code=409,
            code="LESSON_DIVISION_RUNTIME_INVALID",
            message="The frozen material identity is invalid.",
        ) from exc
