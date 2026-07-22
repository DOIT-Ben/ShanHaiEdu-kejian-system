"""Asset-owned exact background reads and immutable PPTX file writes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.models import ArtifactVersion
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.ppt_runtime_contracts import (
    PptAssetPortError,
    PptBackgroundFact,
    PptxFileVersionFact,
    PublishedPptxObject,
)
from apps.api.assets.pptx_writer import SqlAlchemyPptxWriter
from apps.api.assets.project_models import AssetBinding, ProjectAssetSlot
from apps.api.assets.project_repository import ProjectAssetRepository
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.runtime_boundary.ports import WorkflowExecutionContext


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
        return SqlAlchemyPptxWriter(self._session, self._actor).persist(
            execution,
            published,
            page_count=page_count,
            implementation_version=implementation_version,
        )

    def _background_for_page(
        self,
        execution: WorkflowExecutionContext,
        page: Mapping[str, Any],
        *,
        page_spec_version_id: UUID,
        for_update: bool,
    ) -> PptBackgroundFact:
        page_key, position, slot = self._required_background_slot(
            execution,
            page,
            for_update=for_update,
        )
        binding = self._required_background_binding(
            slot,
            page_spec_version_id=page_spec_version_id,
            for_update=for_update,
        )
        record = self._repository.get_file_version(binding.file_asset_version_id)
        if record is None:
            raise _background_invalid()
        version, asset = record
        if not _valid_background_file(asset, version):
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
            width=cast(int, version.width),
            height=cast(int, version.height),
        )

    def _required_background_slot(
        self,
        execution: WorkflowExecutionContext,
        page: Mapping[str, Any],
        *,
        for_update: bool,
    ) -> tuple[str, int, ProjectAssetSlot]:
        page_key = _text(page.get("page_key"))
        position = _positive_int(page.get("page_position"))
        requirements = page.get("page_asset_requirements")
        if not isinstance(requirements, Sequence) or isinstance(
            requirements, (str, bytes, bytearray)
        ):
            raise _background_invalid()
        values = cast(Sequence[object], requirements)
        if len(values) != 1 or not isinstance(values[0], Mapping):
            raise _background_invalid()
        slot_key = _text(cast(Mapping[str, Any], values[0]).get("target_slot"))
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
        return page_key, position, slot

    def _required_background_binding(
        self,
        slot: ProjectAssetSlot,
        *,
        page_spec_version_id: UUID,
        for_update: bool,
    ) -> AssetBinding:
        bindings = self._repository.list_active_bindings(slot.id, for_update=for_update)
        if len(bindings) != 1:
            raise _background_invalid()
        binding = bindings[0]
        if binding.position != 0 or not self._same_page_spec_lineage(
            binding.source_artifact_version_id,
            page_spec_version_id,
        ):
            raise _background_invalid()
        return binding

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


def _valid_background_file(asset: FileAsset, version: FileAssetVersion) -> bool:
    return (
        asset.status == "active"
        and asset.asset_kind == "image"
        and version.scan_status == "clean"
        and version.mime_type == "image/png"
        and version.byte_size > 0
        and version.width is not None
        and version.height is not None
        and version.width > 0
        and version.height > 0
        and _is_sha256(version.sha256)
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
