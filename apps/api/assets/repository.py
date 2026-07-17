"""Tenant-scoped file asset and material parse persistence queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from apps.api.assets.models import FileAsset, FileAssetVersion, MaterialParseVersion
from apps.api.identity.context import ActorContext
from apps.api.identity.models import ProjectMember
from apps.api.uploads.models import SourceMaterial


@dataclass(frozen=True, slots=True)
class MaterialFileRecord:
    material: SourceMaterial
    asset: FileAsset
    current_version: FileAssetVersion


class FileAssetRepository:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def get_for_material(
        self,
        project_id: UUID,
        material_id: UUID,
        *,
        for_update: bool = False,
    ) -> MaterialFileRecord | None:
        statement = (
            select(SourceMaterial, FileAsset, FileAssetVersion)
            .join(FileAsset, FileAsset.id == SourceMaterial.file_asset_id)
            .join(FileAssetVersion, FileAssetVersion.id == FileAsset.current_version_id)
            .where(
                SourceMaterial.id == material_id,
                SourceMaterial.project_id == project_id,
                SourceMaterial.organization_id == self._actor.organization_id,
                SourceMaterial.deleted_at.is_(None),
                FileAsset.organization_id == self._actor.organization_id,
                FileAsset.deleted_at.is_(None),
                FileAssetVersion.organization_id == self._actor.organization_id,
            )
        )
        statement = self._scope_to_member(statement, SourceMaterial.project_id)
        if for_update:
            statement = statement.with_for_update(of=(SourceMaterial, FileAsset))
        row = self._session.execute(statement).one_or_none()
        if row is None:
            return None
        return MaterialFileRecord(
            material=row[0],
            asset=row[1],
            current_version=row[2],
        )

    def get_parse(self, parse_id: UUID, *, for_update: bool = False) -> MaterialParseVersion | None:
        statement = (
            select(MaterialParseVersion)
            .join(SourceMaterial, SourceMaterial.id == MaterialParseVersion.source_material_id)
            .where(
                MaterialParseVersion.id == parse_id,
                MaterialParseVersion.organization_id == self._actor.organization_id,
                SourceMaterial.organization_id == self._actor.organization_id,
                SourceMaterial.deleted_at.is_(None),
            )
        )
        statement = self._scope_to_member(statement, SourceMaterial.project_id)
        if for_update:
            statement = statement.with_for_update(of=MaterialParseVersion)
        return self._session.scalar(statement)

    def list_parse_versions(
        self,
        project_id: UUID,
        material_id: UUID,
    ) -> list[MaterialParseVersion]:
        statement = (
            select(MaterialParseVersion)
            .join(SourceMaterial, SourceMaterial.id == MaterialParseVersion.source_material_id)
            .where(
                SourceMaterial.id == material_id,
                SourceMaterial.project_id == project_id,
                SourceMaterial.organization_id == self._actor.organization_id,
                SourceMaterial.deleted_at.is_(None),
                MaterialParseVersion.organization_id == self._actor.organization_id,
            )
            .order_by(MaterialParseVersion.version_no.desc())
        )
        statement = self._scope_to_member(statement, SourceMaterial.project_id)
        return list(self._session.scalars(statement))

    def lock_material(self, material_id: UUID) -> SourceMaterial | None:
        return self._session.scalar(self._material_statement(material_id).with_for_update())

    def get_material(self, material_id: UUID) -> SourceMaterial | None:
        return self._session.scalar(self._material_statement(material_id))

    def _material_statement(self, material_id: UUID) -> Select[tuple[SourceMaterial]]:
        statement = select(SourceMaterial).where(
            SourceMaterial.id == material_id,
            SourceMaterial.organization_id == self._actor.organization_id,
            SourceMaterial.deleted_at.is_(None),
        )
        return self._scope_to_member(statement, SourceMaterial.project_id)

    def next_parse_version_no(self, material_id: UUID) -> int:
        return (
            self._session.scalar(
                select(func.max(MaterialParseVersion.version_no)).where(
                    MaterialParseVersion.source_material_id == material_id
                )
            )
            or 0
        ) + 1

    def get_file_version(self, version_id: UUID) -> FileAssetVersion | None:
        return self._session.scalar(
            select(FileAssetVersion).where(
                FileAssetVersion.id == version_id,
                FileAssetVersion.organization_id == self._actor.organization_id,
            )
        )

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
