"""Asset-owned immutable PPTX file persistence inside the caller transaction."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.ppt_runtime_contracts import (
    PptAssetPortError,
    PptxFileVersionFact,
    PublishedPptxObject,
)
from apps.api.database import utc_now
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.runtime_boundary.ports import WorkflowExecutionContext

PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class SqlAlchemyPptxWriter:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def persist(
        self,
        execution: WorkflowExecutionContext,
        published: PublishedPptxObject,
        *,
        page_count: int,
        implementation_version: str,
    ) -> PptxFileVersionFact:
        _require_pptx_fact(execution, published, page_count)
        asset = self._pptx_asset(execution)
        version = self._pptx_version(
            asset,
            execution,
            published,
            page_count=page_count,
            implementation_version=implementation_version,
        )
        asset.current_version_id = version.id
        asset.updated_at = utc_now()
        asset.updated_by = self._actor.principal_id
        asset.lock_version += 1
        self._session.flush()
        return _pptx_file_fact(asset, version)

    def _pptx_asset(self, execution: WorkflowExecutionContext) -> FileAsset:
        asset_key = f"pptx:{execution.project_id}:{execution.lesson_unit_id}"
        asset = self._session.scalar(
            select(FileAsset)
            .where(
                FileAsset.organization_id == self._actor.organization_id,
                FileAsset.asset_key == asset_key,
                FileAsset.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if asset is None:
            asset = FileAsset(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                asset_key=asset_key,
                asset_kind="pptx",
                current_version_id=None,
                status="active",
                retention_class="project_asset",
                created_by=self._actor.principal_id,
                updated_by=self._actor.principal_id,
            )
            self._session.add(asset)
            self._session.flush()
        elif asset.asset_kind != "pptx" or asset.status != "active":
            raise _error(
                "PPT_RUNTIME_PPTX_IDENTITY_CONFLICT",
                "the stable PPTX file identity conflicts with an existing asset",
            )
        return asset

    def _pptx_version(
        self,
        asset: FileAsset,
        execution: WorkflowExecutionContext,
        published: PublishedPptxObject,
        *,
        page_count: int,
        implementation_version: str,
    ) -> FileAssetVersion:
        version = self._session.scalar(
            select(FileAssetVersion).where(
                FileAssetVersion.organization_id == self._actor.organization_id,
                FileAssetVersion.file_asset_id == asset.id,
                FileAssetVersion.storage_bucket == published.bucket,
                FileAssetVersion.storage_key == published.key,
                FileAssetVersion.sha256 == published.sha256,
            )
        )
        if version is not None:
            return version
        version = self._new_pptx_version(
            asset,
            execution,
            published,
            page_count=page_count,
            implementation_version=implementation_version,
        )
        self._session.add(version)
        self._session.flush()
        return version

    def _new_pptx_version(
        self,
        asset: FileAsset,
        execution: WorkflowExecutionContext,
        published: PublishedPptxObject,
        *,
        page_count: int,
        implementation_version: str,
    ) -> FileAssetVersion:
        return FileAssetVersion(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            file_asset_id=asset.id,
            version_no=self._next_file_version_no(asset.id),
            storage_bucket=published.bucket,
            storage_key=published.key,
            mime_type=published.mime_type,
            byte_size=published.size_bytes,
            sha256=published.sha256,
            etag=published.etag,
            width=None,
            height=None,
            duration_ms=None,
            page_count=page_count,
            scan_status="clean",
            metadata_json={
                "project_id": str(execution.project_id),
                "lesson_unit_id": str(execution.lesson_unit_id),
                "lesson_key": execution.lesson_key,
                "source_node_run_id": str(execution.node_run_id),
                "implementation_version": implementation_version,
            },
            derived_from_version_id=None,
            created_at=utc_now(),
            created_by=self._actor.principal_id,
        )

    def _next_file_version_no(self, asset_id: UUID) -> int:
        latest = self._session.scalar(
            select(func.coalesce(func.max(FileAssetVersion.version_no), 0)).where(
                FileAssetVersion.file_asset_id == asset_id
            )
        )
        return int(latest or 0) + 1


def _require_pptx_fact(
    execution: WorkflowExecutionContext,
    published: PublishedPptxObject,
    page_count: int,
) -> None:
    if (
        execution.lesson_unit_id is None
        or execution.lesson_key is None
        or published.mime_type != PPTX_MEDIA_TYPE
        or published.size_bytes <= 0
        or not _is_sha256(published.sha256)
        or not published.etag
        or page_count <= 0
    ):
        raise _error(
            "PPT_RUNTIME_PPTX_FACT_INVALID",
            "the published PPTX object fact is invalid",
        )


def _pptx_file_fact(asset: FileAsset, version: FileAssetVersion) -> PptxFileVersionFact:
    return PptxFileVersionFact(
        file_asset_id=asset.id,
        file_asset_version_id=version.id,
        bucket=version.storage_bucket,
        key=version.storage_key,
        etag=version.etag,
        mime_type=version.mime_type,
        size_bytes=version.byte_size,
        sha256=version.sha256,
        page_count=cast(int, version.page_count),
    )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _error(code: str, message: str) -> PptAssetPortError:
    return PptAssetPortError(code, message)
