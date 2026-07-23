"""Asset facts exposed to exact linked-file artifact approval."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.identity.context import ActorContext


@dataclass(frozen=True, slots=True)
class LinkedFileApprovalFact:
    file_asset_id: UUID
    file_asset_version_id: UUID
    mime_type: str
    size_bytes: int
    sha256: str
    page_count: int


class LinkedFileApprovalReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def current_pptx(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID | None,
        file_asset_version_id: UUID,
    ) -> LinkedFileApprovalFact | None:
        row = self._session.execute(
            select(FileAssetVersion, FileAsset)
            .join(FileAsset, FileAsset.id == FileAssetVersion.file_asset_id)
            .where(
                FileAssetVersion.id == file_asset_version_id,
                FileAssetVersion.organization_id == self._actor.organization_id,
                FileAssetVersion.scan_status == "clean",
                FileAssetVersion.page_count.is_not(None),
                FileAsset.id == FileAssetVersion.file_asset_id,
                FileAsset.organization_id == self._actor.organization_id,
                FileAsset.asset_kind == "pptx",
                FileAsset.status == "active",
                FileAsset.current_version_id == FileAssetVersion.id,
                FileAsset.deleted_at.is_(None),
            )
            .with_for_update(of=FileAsset)
        ).one_or_none()
        if row is None:
            return None
        version, asset = row
        metadata = version.metadata_json
        if (
            metadata.get("project_id") != str(project_id)
            or metadata.get("lesson_unit_id")
            != (str(lesson_unit_id) if lesson_unit_id is not None else None)
            or version.page_count is None
            or version.page_count <= 0
        ):
            return None
        return LinkedFileApprovalFact(
            file_asset_id=asset.id,
            file_asset_version_id=version.id,
            mime_type=version.mime_type,
            size_bytes=version.byte_size,
            sha256=version.sha256,
            page_count=version.page_count,
        )
