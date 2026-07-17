"""Tenant-safe persistence queries for project asset slots and bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.project_models import AssetBinding, ProjectAssetSlot
from apps.api.identity.context import ActorContext
from apps.api.identity.models import ProjectMember
from apps.api.projects.models import Project


@dataclass(frozen=True, slots=True)
class ProjectAssetSlotView:
    slot: ProjectAssetSlot
    active_bindings: tuple[AssetBinding, ...]


class ProjectAssetRepository:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def get_slot(self, slot_id: UUID, *, for_update: bool = False) -> ProjectAssetSlot | None:
        statement = self._visible_slots().where(ProjectAssetSlot.id == slot_id)
        if for_update:
            statement = statement.with_for_update(of=ProjectAssetSlot)
        return self._session.scalar(statement)

    def get_slot_by_key(
        self,
        project_id: UUID,
        slot_key: str,
        *,
        for_update: bool = False,
    ) -> ProjectAssetSlot | None:
        statement = self._visible_slots().where(
            ProjectAssetSlot.project_id == project_id,
            ProjectAssetSlot.slot_key == slot_key,
        )
        if for_update:
            statement = statement.with_for_update(of=ProjectAssetSlot)
        return self._session.scalar(statement)

    def get_binding(self, binding_id: UUID, *, for_update: bool = False) -> AssetBinding | None:
        statement = (
            select(AssetBinding)
            .join(
                ProjectAssetSlot,
                ProjectAssetSlot.id == AssetBinding.project_asset_slot_id,
            )
            .join(Project, Project.id == ProjectAssetSlot.project_id)
            .where(
                AssetBinding.id == binding_id,
                AssetBinding.organization_id == self._actor.organization_id,
                ProjectAssetSlot.organization_id == self._actor.organization_id,
                Project.organization_id == self._actor.organization_id,
                Project.deleted_at.is_(None),
                ProjectAssetSlot.deleted_at.is_(None),
            )
        )
        statement = self._scope_to_member(statement, ProjectAssetSlot.project_id)
        if for_update:
            statement = statement.with_for_update(of=AssetBinding)
        return self._session.scalar(statement)

    def list_active_bindings(
        self,
        slot_id: UUID,
        *,
        for_update: bool = False,
    ) -> list[AssetBinding]:
        statement = (
            select(AssetBinding)
            .where(
                AssetBinding.project_asset_slot_id == slot_id,
                AssetBinding.organization_id == self._actor.organization_id,
                AssetBinding.is_active,
            )
            .order_by(AssetBinding.position, AssetBinding.id)
        )
        if for_update:
            statement = statement.with_for_update(of=AssetBinding)
        return list(self._session.scalars(statement))

    def get_file_version(
        self,
        version_id: UUID,
    ) -> tuple[FileAssetVersion, FileAsset] | None:
        row = self._session.execute(
            select(FileAssetVersion, FileAsset)
            .join(FileAsset, FileAsset.id == FileAssetVersion.file_asset_id)
            .where(
                FileAssetVersion.id == version_id,
                FileAssetVersion.organization_id == self._actor.organization_id,
                FileAsset.organization_id == self._actor.organization_id,
                FileAsset.deleted_at.is_(None),
            )
        ).one_or_none()
        return None if row is None else (row[0], row[1])

    def get_artifact_version(
        self,
        version_id: UUID,
    ) -> tuple[ArtifactVersion, Artifact] | None:
        statement = (
            select(ArtifactVersion, Artifact)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                ArtifactVersion.id == version_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                Artifact.organization_id == self._actor.organization_id,
                Artifact.deleted_at.is_(None),
            )
        )
        statement = self._scope_to_member(statement, Artifact.project_id)
        row = self._session.execute(statement).one_or_none()
        return None if row is None else (row[0], row[1])

    def list_slots_page(
        self,
        project_id: UUID,
        *,
        cursor: UUID | None,
        limit: int,
        lesson_unit_id: UUID | None,
        slot_key: str | None,
    ) -> tuple[list[ProjectAssetSlotView], str | None]:
        statement = self._visible_slots().where(ProjectAssetSlot.project_id == project_id)
        if cursor is not None:
            statement = statement.where(ProjectAssetSlot.id > cursor)
        if lesson_unit_id is not None:
            statement = statement.where(ProjectAssetSlot.lesson_unit_id == lesson_unit_id)
        if slot_key is not None:
            statement = statement.where(ProjectAssetSlot.slot_key == slot_key)
        slots = list(
            self._session.scalars(statement.order_by(ProjectAssetSlot.id).limit(limit + 1))
        )
        next_cursor = str(slots[limit - 1].id) if len(slots) > limit else None
        page = slots[:limit]
        if not page:
            return [], next_cursor
        bindings = list(
            self._session.scalars(
                select(AssetBinding)
                .where(
                    AssetBinding.organization_id == self._actor.organization_id,
                    AssetBinding.project_asset_slot_id.in_([slot.id for slot in page]),
                    AssetBinding.is_active,
                )
                .order_by(
                    AssetBinding.project_asset_slot_id,
                    AssetBinding.position,
                    AssetBinding.id,
                )
            )
        )
        by_slot: dict[UUID, list[AssetBinding]] = {slot.id: [] for slot in page}
        for binding in bindings:
            by_slot[binding.project_asset_slot_id].append(binding)
        return [
            ProjectAssetSlotView(slot=slot, active_bindings=tuple(by_slot[slot.id]))
            for slot in page
        ], next_cursor

    def _visible_slots(self) -> Select[tuple[ProjectAssetSlot]]:
        statement = (
            select(ProjectAssetSlot)
            .join(Project, Project.id == ProjectAssetSlot.project_id)
            .where(
                ProjectAssetSlot.organization_id == self._actor.organization_id,
                ProjectAssetSlot.deleted_at.is_(None),
                Project.organization_id == self._actor.organization_id,
                Project.deleted_at.is_(None),
            )
        )
        return self._scope_to_member(statement, ProjectAssetSlot.project_id)

    def _scope_to_member(
        self,
        statement: Select[Any],
        project_column: InstrumentedAttribute[UUID],
    ) -> Select[Any]:
        if self._actor.user_id is None or self._actor.is_system:
            return statement
        return statement.join(
            ProjectMember,
            (ProjectMember.project_id == project_column)
            & (ProjectMember.user_id == self._actor.user_id),
        )
