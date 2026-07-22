"""Asset-owned exact background reads and immutable PPTX file writes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.artifacts.models import ArtifactVersion
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.ppt_runtime_contracts import (
    PptAssetPortError,
    PptBackgroundFact,
    PptxFileVersionFact,
    PublishedPptxObject,
)
from apps.api.assets.project_repository import ProjectAssetRepository
from apps.api.database import utc_now
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.runtime_boundary.ports import WorkflowExecutionContext

PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class SqlAlchemyPptAssetPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = ProjectAssetRepository(session, actor)

    def resolve_backgrounds(
        self,
        execution: WorkflowExecutionContext,
        *,
        page_spec_version_id: UUID,
        page_spec_content: Mapping[str, Any],
        for_update: bool,
    ) -> tuple[PptBackgroundFact, ...]:
        ProjectAccessService(self._session, self._actor).require(
            execution.project_id,
            ProjectAction.GENERATE,
            for_update=for_update,
        )
        pages = _page_sources(page_spec_content)
        facts = tuple(
            self._background_for_page(
                execution,
                page,
                page_spec_version_id=page_spec_version_id,
                for_update=for_update,
            )
            for page in pages
        )
        if len({item.file_asset_version_id for item in facts}) != len(facts):
            raise _error(
                "PPT_RUNTIME_BACKGROUND_REUSED",
                "each PPT page must bind its own exact background version",
            )
        return facts

    def verify_backgrounds(
        self,
        execution: WorkflowExecutionContext,
        *,
        page_spec_version_id: UUID,
        page_spec_content: Mapping[str, Any],
        expected: tuple[PptBackgroundFact, ...],
    ) -> None:
        current = self.resolve_backgrounds(
            execution,
            page_spec_version_id=page_spec_version_id,
            page_spec_content=page_spec_content,
            for_update=True,
        )
        if current != expected:
            raise _error(
                "PPT_RUNTIME_BACKGROUND_CHANGED",
                "an exact PPT background binding changed before commit",
            )

    def persist_pptx(
        self,
        execution: WorkflowExecutionContext,
        published: PublishedPptxObject,
        *,
        page_count: int,
        implementation_version: str,
    ) -> PptxFileVersionFact:
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
        existing = self._session.scalar(
            select(FileAssetVersion).where(
                FileAssetVersion.organization_id == self._actor.organization_id,
                FileAssetVersion.file_asset_id == asset.id,
                FileAssetVersion.storage_bucket == published.bucket,
                FileAssetVersion.storage_key == published.key,
                FileAssetVersion.sha256 == published.sha256,
            )
        )
        if existing is None:
            version_no = (
                int(
                    self._session.scalar(
                        select(func.coalesce(func.max(FileAssetVersion.version_no), 0)).where(
                            FileAssetVersion.file_asset_id == asset.id
                        )
                    )
                    or 0
                )
                + 1
            )
            existing = FileAssetVersion(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                file_asset_id=asset.id,
                version_no=version_no,
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
            self._session.add(existing)
            self._session.flush()
        asset.current_version_id = existing.id
        asset.updated_at = utc_now()
        asset.updated_by = self._actor.principal_id
        asset.lock_version += 1
        self._session.flush()
        return PptxFileVersionFact(
            file_asset_id=asset.id,
            file_asset_version_id=existing.id,
            bucket=existing.storage_bucket,
            key=existing.storage_key,
            etag=existing.etag,
            mime_type=existing.mime_type,
            size_bytes=existing.byte_size,
            sha256=existing.sha256,
            page_count=cast(int, existing.page_count),
        )

    def _background_for_page(
        self,
        execution: WorkflowExecutionContext,
        page: Mapping[str, Any],
        *,
        page_spec_version_id: UUID,
        for_update: bool,
    ) -> PptBackgroundFact:
        page_key = _text(page.get("page_key"))
        position = _positive_int(page.get("page_position"))
        requirements = page.get("page_asset_requirements")
        if not isinstance(requirements, Sequence) or isinstance(
            requirements,
            (str, bytes, bytearray),
        ):
            raise _background_invalid()
        typed_requirements = cast(Sequence[object], requirements)
        if len(typed_requirements) != 1 or not isinstance(typed_requirements[0], Mapping):
            raise _background_invalid()
        slot_key = _text(cast(Mapping[str, Any], typed_requirements[0]).get("target_slot"))
        slot = self._repository.get_slot_by_key(
            execution.project_id,
            slot_key,
            for_update=for_update,
        )
        if (
            slot is None
            or slot.organization_id != self._actor.organization_id
            or slot.lesson_unit_id != execution.lesson_unit_id
            or slot.asset_type != "image"
            or slot.cardinality != "one"
            or not slot.required
            or slot.status != "satisfied"
        ):
            raise _background_invalid()
        bindings = self._repository.list_active_bindings(slot.id, for_update=for_update)
        if len(bindings) != 1:
            raise _background_invalid()
        binding = bindings[0]
        if binding.position != 0 or not self._same_page_spec_lineage(
            binding.source_artifact_version_id,
            page_spec_version_id,
        ):
            raise _background_invalid()
        record = self._repository.get_file_version(binding.file_asset_version_id)
        if record is None:
            raise _background_invalid()
        version, asset = record
        if (
            asset.status != "active"
            or asset.asset_kind != "image"
            or version.scan_status != "clean"
            or version.mime_type != "image/png"
            or version.byte_size <= 0
            or version.width is None
            or version.height is None
            or version.width <= 0
            or version.height <= 0
            or len(version.sha256) != 64
        ):
            raise _background_invalid()
        return PptBackgroundFact(
            page_key=page_key,
            position=position,
            slot_key=slot.slot_key,
            binding_id=binding.id,
            file_asset_id=asset.id,
            file_asset_version_id=version.id,
            storage_bucket=version.storage_bucket,
            storage_key=version.storage_key,
            mime_type=version.mime_type,
            size_bytes=version.byte_size,
            sha256=version.sha256,
            width=version.width,
            height=version.height,
        )

    def _same_page_spec_lineage(
        self,
        source_version_id: UUID | None,
        current_version_id: UUID,
    ) -> bool:
        if source_version_id is None:
            return False
        source = self._session.get(ArtifactVersion, source_version_id)
        current = self._session.get(ArtifactVersion, current_version_id)
        return bool(
            source is not None
            and current is not None
            and source.organization_id == self._actor.organization_id
            and current.organization_id == self._actor.organization_id
            and source.artifact_id == current.artifact_id
        )


def _page_sources(content: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = content.get("page_specs")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)) or not raw:
        raise _error(
            "PPT_RUNTIME_PAGE_SPECS_INVALID",
            "the exact page specification set is missing",
        )
    pages = tuple(cast(Sequence[object], raw))
    if any(not isinstance(page, Mapping) for page in pages):
        raise _error(
            "PPT_RUNTIME_PAGE_SPECS_INVALID",
            "the exact page specification set is invalid",
        )
    typed = cast(tuple[Mapping[str, Any], ...], pages)
    positions = [_positive_int(page.get("page_position")) for page in typed]
    keys = [_text(page.get("page_key")) for page in typed]
    if positions != list(range(1, len(typed) + 1)) or len(set(keys)) != len(keys):
        raise _error(
            "PPT_RUNTIME_PAGE_SPECS_INVALID",
            "the exact page order or keys are invalid",
        )
    return typed


def _background_invalid() -> PptAssetPortError:
    return _error(
        "PPT_RUNTIME_BACKGROUND_INVALID",
        "each page requires one exact clean background bound from its page specification",
    )


def _text(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("text value is required")
    return value


def _positive_int(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("positive integer is required")
    return value


def _sha256(value: object) -> str:
    text = _text(value)
    if not _is_sha256(text):
        raise ValueError("sha256 is invalid")
    return text


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _error(code: str, message: str) -> PptAssetPortError:
    return PptAssetPortError(code, message)
