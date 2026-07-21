"""Asset-owned exact source adapter for quality validation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifact_quality.contracts import QualitySource
from apps.api.assets.execution_port import AssetExecutionPortError
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.repository import FileAssetRepository
from apps.api.identity.context import ActorContext
from apps.api.runtime_boundary.ports import WorkflowExecutionContext


class SqlAlchemyAssetQualitySourcePort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def load(
        self,
        execution: WorkflowExecutionContext,
        *,
        contract_ref: str,
        source_id: UUID,
        source_version_id: UUID,
    ) -> QualitySource:
        if not contract_ref.startswith("asset:") or not contract_ref.removeprefix("asset:"):
            raise AssetExecutionPortError(
                "QUALITY_SOURCE_CONTRACT_UNKNOWN",
                "the quality asset source contract is not registered",
            )
        asset_kind = contract_ref.removeprefix("asset:")
        row = self._session.execute(
            select(FileAssetVersion, FileAsset)
            .join(FileAsset, FileAsset.id == FileAssetVersion.file_asset_id)
            .where(
                FileAssetVersion.id == source_version_id,
                FileAssetVersion.organization_id == self._actor.organization_id,
                FileAssetVersion.scan_status == "clean",
                FileAsset.id == source_id,
                FileAsset.organization_id == self._actor.organization_id,
                FileAsset.asset_kind == asset_kind,
                FileAsset.status == "active",
                FileAsset.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            raise AssetExecutionPortError(
                "QUALITY_SOURCE_SCOPE_INVALID",
                "the exact file-asset quality source is unavailable in the fixed scope",
            )
        version, asset = row
        return QualitySource(
            source_type="asset",
            source_id=asset.id,
            source_version_id=version.id,
            content_hash=version.sha256,
            content={
                "asset_kind": asset.asset_kind,
                "storage_bucket": version.storage_bucket,
                "storage_key": version.storage_key,
                "mime_type": version.mime_type,
                "byte_size": version.byte_size,
                "sha256": version.sha256,
                "width": version.width,
                "height": version.height,
                "duration_ms": version.duration_ms,
                "page_count": version.page_count,
                "metadata": version.metadata_json,
            },
        )

    def load_supporting(
        self,
        project_id: UUID,
        *,
        contract_ref: str,
        source_id: UUID,
        source_version_id: UUID,
    ) -> QualitySource:
        if contract_ref != "content:material_evidence":
            raise AssetExecutionPortError(
                "QUALITY_SUPPORTING_CONTRACT_UNKNOWN",
                "the quality supporting-input contract is not registered",
            )
        version = FileAssetRepository(self._session, self._actor).get_succeeded_parse_for_project(
            project_id,
            source_id,
            source_version_id,
        )
        if version is None:
            raise AssetExecutionPortError(
                "QUALITY_SUPPORTING_SCOPE_INVALID",
                "the exact material evidence is unavailable in the fixed project scope",
            )
        if version.content_json is None or version.text_checksum is None:
            raise AssetExecutionPortError(
                "QUALITY_SUPPORTING_SOURCE_INVALID",
                "the material evidence parse is incomplete",
            )
        return QualitySource(
            source_type="asset",
            source_id=version.source_material_id,
            source_version_id=version.id,
            content_hash=version.text_checksum,
            content=version.content_json,
        )
