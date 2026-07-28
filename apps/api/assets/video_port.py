"""Asset-owned reads and writes for the video golden slice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.project_models import AssetBinding, ProjectAssetSlot
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7


@dataclass(frozen=True, slots=True)
class VideoKeyframe:
    version_id: UUID
    mime_type: str
    slot_key: str


@dataclass(frozen=True, slots=True)
class VideoFileVersion:
    id: UUID
    storage_bucket: str
    storage_key: str
    mime_type: str
    byte_size: int
    sha256: str
    duration_ms: int | None
    scan_status: str


@dataclass(frozen=True, slots=True)
class GeneratedVideoFile:
    storage_bucket: str
    storage_key: str
    byte_size: int
    sha256: str
    etag: str
    width: int | None
    height: int | None
    duration_ms: int
    derived_from_version_id: UUID
    metadata: dict[str, Any]


class VideoAssetPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def keyframe(
        self, project_id: UUID, lesson_id: UUID, version_id: UUID, *, for_update: bool = False
    ) -> tuple[VideoKeyframe | None, bool]:
        version_row = self._session.execute(
            select(FileAssetVersion, FileAsset)
            .join(FileAsset, FileAsset.id == FileAssetVersion.file_asset_id)
            .where(
                FileAssetVersion.id == version_id,
                FileAssetVersion.organization_id == self._actor.organization_id,
                FileAsset.organization_id == self._actor.organization_id,
                FileAsset.status == "active",
                FileAsset.deleted_at.is_(None),
            )
        ).one_or_none()
        if version_row is None:
            return None, False
        version, asset = version_row
        if (
            asset.asset_kind != "image"
            or not version.mime_type.startswith("image/")
            or version.scan_status != "clean"
        ):
            return None, True
        statement = (
            select(ProjectAssetSlot)
            .join(AssetBinding, AssetBinding.project_asset_slot_id == ProjectAssetSlot.id)
            .where(
                ProjectAssetSlot.organization_id == self._actor.organization_id,
                ProjectAssetSlot.project_id == project_id,
                ProjectAssetSlot.lesson_unit_id == lesson_id,
                ProjectAssetSlot.asset_type == "image",
                ProjectAssetSlot.status == "satisfied",
                ProjectAssetSlot.deleted_at.is_(None),
                AssetBinding.organization_id == self._actor.organization_id,
                AssetBinding.file_asset_version_id == version_id,
                AssetBinding.is_active.is_(True),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=ProjectAssetSlot)
        slot = self._session.scalar(statement)
        if slot is None:
            return None, True
        return VideoKeyframe(version.id, version.mime_type, slot.slot_key), True

    def current_keyframe(self, project_id: UUID, lesson_id: UUID) -> VideoKeyframe | None:
        row = self._session.execute(
            select(ProjectAssetSlot.slot_key, FileAssetVersion.id, FileAssetVersion.mime_type)
            .join(AssetBinding, AssetBinding.project_asset_slot_id == ProjectAssetSlot.id)
            .join(FileAssetVersion, FileAssetVersion.id == AssetBinding.file_asset_version_id)
            .where(
                ProjectAssetSlot.organization_id == self._actor.organization_id,
                ProjectAssetSlot.project_id == project_id,
                ProjectAssetSlot.lesson_unit_id == lesson_id,
                ProjectAssetSlot.asset_type == "image",
                ProjectAssetSlot.slot_key.like("lesson.%.video.keyframe"),
                ProjectAssetSlot.status == "satisfied",
                ProjectAssetSlot.deleted_at.is_(None),
                AssetBinding.organization_id == self._actor.organization_id,
                AssetBinding.is_active.is_(True),
                FileAssetVersion.organization_id == self._actor.organization_id,
                FileAssetVersion.scan_status == "clean",
                FileAssetVersion.mime_type.like("image/%"),
            )
            .order_by(AssetBinding.id.desc())
            .limit(1)
        ).one_or_none()
        if row is None:
            return None
        return VideoKeyframe(row.id, row.mime_type, row.slot_key)

    def file_version(self, version_id: UUID) -> VideoFileVersion | None:
        version = self._session.scalar(
            select(FileAssetVersion).where(
                FileAssetVersion.id == version_id,
                FileAssetVersion.organization_id == self._actor.organization_id,
            )
        )
        return _file_fact(version)

    def persist_generated(
        self, job_id: UUID, payload: GeneratedVideoFile, *, now: datetime
    ) -> VideoFileVersion:
        asset = FileAsset(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            asset_key=f"video.golden:{job_id}",
            asset_kind="video",
            status="active",
            retention_class="project_asset",
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(asset)
        self._session.flush()
        version = FileAssetVersion(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            file_asset_id=asset.id,
            version_no=1,
            storage_bucket=payload.storage_bucket,
            storage_key=payload.storage_key,
            mime_type="video/mp4",
            byte_size=payload.byte_size,
            sha256=payload.sha256,
            etag=payload.etag,
            width=payload.width,
            height=payload.height,
            duration_ms=payload.duration_ms,
            scan_status="clean",
            metadata_json=payload.metadata,
            derived_from_version_id=payload.derived_from_version_id,
            created_at=now,
            created_by=self._actor.principal_id,
        )
        self._session.add(version)
        self._session.flush()
        asset.current_version_id = version.id
        fact = _file_fact(version)
        assert fact is not None
        return fact

    def saved_binding_id(self, result_id: UUID) -> UUID | None:
        return self._session.scalar(
            select(AssetBinding.id)
            .join(ProjectAssetSlot)
            .where(
                AssetBinding.organization_id == self._actor.organization_id,
                AssetBinding.source_generation_result_id == result_id,
                AssetBinding.is_active.is_(True),
                ProjectAssetSlot.organization_id == self._actor.organization_id,
                ProjectAssetSlot.deleted_at.is_(None),
            )
            .order_by(AssetBinding.id.desc())
            .limit(1)
        )

    def target_has_active_binding(self, project_id: UUID, slot_key: str) -> bool:
        return (
            self._session.scalar(
                select(AssetBinding.id)
                .join(ProjectAssetSlot)
                .where(
                    ProjectAssetSlot.organization_id == self._actor.organization_id,
                    ProjectAssetSlot.project_id == project_id,
                    ProjectAssetSlot.slot_key == slot_key,
                    ProjectAssetSlot.deleted_at.is_(None),
                    AssetBinding.organization_id == self._actor.organization_id,
                    AssetBinding.is_active.is_(True),
                )
                .limit(1)
            )
            is not None
        )


def _file_fact(version: FileAssetVersion | None) -> VideoFileVersion | None:
    if version is None:
        return None
    return VideoFileVersion(
        id=version.id,
        storage_bucket=version.storage_bucket,
        storage_key=version.storage_key,
        mime_type=version.mime_type,
        byte_size=version.byte_size,
        sha256=version.sha256,
        duration_ms=version.duration_ms,
        scan_status=version.scan_status,
    )
