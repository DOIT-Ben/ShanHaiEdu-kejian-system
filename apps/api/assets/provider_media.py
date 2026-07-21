"""Asset-owned read boundary for provider-visible temporary media."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.assets.models import FileAsset, FileAssetVersion


@dataclass(frozen=True, slots=True)
class ProviderMediaAssetVersion:
    """Validated immutable image facts without storage transport details."""

    id: UUID
    organization_id: UUID
    storage_bucket: str
    storage_key: str
    mime_type: str
    byte_size: int
    sha256: str


class ProviderMediaAssetReader(Protocol):
    def get_clean_image_version(
        self,
        *,
        organization_id: UUID,
        file_version_id: UUID,
    ) -> ProviderMediaAssetVersion | None: ...


class SqlAlchemyProviderMediaAssetReader:
    """Reads only active, clean immutable versions for one trusted organization."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_clean_image_version(
        self,
        *,
        organization_id: UUID,
        file_version_id: UUID,
    ) -> ProviderMediaAssetVersion | None:
        # The shared session factory disables autoflush. Persist a same-transaction
        # revocation before deciding whether provider-visible media is still eligible.
        self._session.flush()
        row = self._session.execute(
            select(FileAssetVersion)
            .join(FileAsset, FileAsset.id == FileAssetVersion.file_asset_id)
            .where(
                FileAssetVersion.id == file_version_id,
                FileAssetVersion.organization_id == organization_id,
                FileAsset.organization_id == organization_id,
                FileAsset.deleted_at.is_(None),
                FileAsset.status == "active",
                FileAssetVersion.scan_status == "clean",
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return ProviderMediaAssetVersion(
            id=row.id,
            organization_id=row.organization_id,
            storage_bucket=row.storage_bucket,
            storage_key=row.storage_key,
            mime_type=row.mime_type,
            byte_size=row.byte_size,
            sha256=row.sha256,
        )
