"""Atomic project asset slot declaration, binding, and aggregation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
    ReplaceMode,
)
from apps.api.assets.project_models import AssetBinding, ProjectAssetSlot
from apps.api.assets.project_repository import ProjectAssetRepository, ProjectAssetSlotView
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.lessons.repository import LessonRepository
from apps.api.reliability.events import EventResource, EventWriter


class ProjectAssetService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = ProjectAssetRepository(session, actor)

    def declare_slot(
        self,
        project_id: UUID,
        declaration: AssetSlotDeclaration,
        *,
        request_id: str | None,
    ) -> ProjectAssetSlot:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.EDIT,
            for_update=True,
        )
        self._require_lesson(project_id, declaration.lesson_unit_id)
        existing = self._repository.get_slot_by_key(
            project_id,
            declaration.slot_key,
            for_update=True,
        )
        target_contract = declaration.target_contract.model_dump(mode="json")
        if existing is not None:
            if (
                existing.lesson_unit_id == declaration.lesson_unit_id
                and existing.asset_type == declaration.asset_type
                and existing.cardinality == declaration.cardinality.value
                and existing.required == declaration.required
                and existing.target_contract_json == target_contract
            ):
                return existing
            raise ApiError(
                status_code=409,
                code="ASSET_SLOT_CONFLICT",
                message="The slot key is already declared with a different contract.",
            )
        slot = ProjectAssetSlot(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=project_id,
            lesson_unit_id=declaration.lesson_unit_id,
            slot_key=declaration.slot_key,
            asset_type=declaration.asset_type,
            cardinality=declaration.cardinality.value,
            required=declaration.required,
            status="empty",
            target_contract_json=target_contract,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(slot)
        self._session.flush()
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=project_id,
            event_type="project_asset.slot.declared",
            resource=EventResource(type="project_asset_slot", id=slot.id),
            payload={
                "slot_key": slot.slot_key,
                "asset_type": slot.asset_type,
                "cardinality": slot.cardinality,
                "required": slot.required,
            },
            request_id=request_id,
        )
        return slot

    def bind(
        self,
        slot_id: UUID,
        *,
        file_asset_version_id: UUID,
        source_artifact_version_id: UUID | None,
        source_generation_result_id: UUID | None = None,
        save_operation_id: UUID | None = None,
        replace_mode: ReplaceMode,
        position: int | None,
        request_id: str | None,
    ) -> AssetBinding:
        slot = self._require_slot(slot_id, ProjectAction.EDIT)
        file_version, file_asset = self._require_file_version(file_asset_version_id)
        self._validate_file(
            slot, file_asset.asset_kind, file_version.mime_type, file_version.scan_status
        )
        self._validate_artifact_source(slot, source_artifact_version_id)
        active = self._repository.list_active_bindings(slot.id, for_update=True)
        resolved_position, replaced = self._resolve_position(
            slot,
            active,
            replace_mode=replace_mode,
            position=position,
        )
        now = utc_now()
        if replaced is not None:
            self._deactivate(replaced, now=now)
        binding = AssetBinding(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_asset_slot_id=slot.id,
            file_asset_version_id=file_version.id,
            source_generation_result_id=source_generation_result_id,
            source_artifact_version_id=source_artifact_version_id,
            save_operation_id=save_operation_id,
            position=resolved_position,
            is_active=True,
            bound_at=now,
            bound_by=self._actor.principal_id,
            unbound_at=None,
            unbound_by=None,
        )
        self._session.add(binding)
        self._touch_slot(slot, status="satisfied", now=now)
        self._session.flush()
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=slot.project_id,
            event_type=(
                "project_asset.binding.replaced"
                if replaced is not None
                else "project_asset.binding.created"
            ),
            resource=EventResource(type="asset_binding", id=binding.id),
            payload={
                "slot_id": str(slot.id),
                "slot_key": slot.slot_key,
                "file_asset_version_id": str(file_version.id),
                "source_artifact_version_id": (
                    str(source_artifact_version_id)
                    if source_artifact_version_id is not None
                    else None
                ),
                "source_generation_result_id": (
                    str(source_generation_result_id)
                    if source_generation_result_id is not None
                    else None
                ),
                "save_operation_id": (
                    str(save_operation_id) if save_operation_id is not None else None
                ),
                "position": binding.position,
                "replaced_binding_id": str(replaced.id) if replaced is not None else None,
            },
            request_id=request_id,
        )
        return binding

    def unbind(self, binding_id: UUID, *, request_id: str | None) -> AssetBinding:
        visible = self._repository.get_binding(binding_id)
        if visible is None:
            raise self._binding_not_found()
        slot = self._require_slot(visible.project_asset_slot_id, ProjectAction.EDIT)
        binding = self._repository.get_binding(binding_id, for_update=True)
        if binding is None:
            raise self._binding_not_found()
        if not binding.is_active:
            return binding
        now = utc_now()
        self._deactivate(binding, now=now)
        self._session.flush()
        remaining = self._repository.list_active_bindings(slot.id, for_update=True)
        self._touch_slot(slot, status="satisfied" if remaining else "empty", now=now)
        self._session.flush()
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=slot.project_id,
            event_type="project_asset.binding.unbound",
            resource=EventResource(type="asset_binding", id=binding.id),
            payload={
                "slot_id": str(slot.id),
                "slot_key": slot.slot_key,
                "position": binding.position,
            },
            request_id=request_id,
        )
        return binding

    def list_slots(
        self,
        project_id: UUID,
        *,
        cursor: UUID | None,
        limit: int,
        lesson_unit_id: UUID | None,
        slot_key: str | None,
    ) -> tuple[list[ProjectAssetSlotView], str | None]:
        ProjectAccessService(self._session, self._actor).require(project_id, ProjectAction.VIEW)
        if lesson_unit_id is not None:
            self._require_lesson(project_id, lesson_unit_id)
        return self._repository.list_slots_page(
            project_id,
            cursor=cursor,
            limit=limit,
            lesson_unit_id=lesson_unit_id,
            slot_key=slot_key,
        )

    def _require_slot(self, slot_id: UUID, action: ProjectAction) -> ProjectAssetSlot:
        visible = self._repository.get_slot(slot_id)
        if visible is None:
            raise self._slot_not_found()
        ProjectAccessService(self._session, self._actor).require(
            visible.project_id,
            action,
            for_update=True,
        )
        locked = self._repository.get_slot(slot_id, for_update=True)
        if locked is None:
            raise self._slot_not_found()
        return locked

    def _require_lesson(self, project_id: UUID, lesson_unit_id: UUID | None) -> None:
        if lesson_unit_id is None:
            return
        lesson = LessonRepository(self._session, self._actor).get(lesson_unit_id)
        if lesson is None or lesson.project_id != project_id or lesson.status != "active":
            raise ApiError(
                status_code=422,
                code="ASSET_SLOT_LESSON_MISMATCH",
                message="The asset slot lesson does not belong to the active project lessons.",
            )

    def _require_file_version(self, version_id: UUID) -> tuple[FileAssetVersion, FileAsset]:
        record = self._repository.get_file_version(version_id)
        if record is None:
            raise ApiError(
                status_code=404,
                code="FILE_ASSET_VERSION_NOT_FOUND",
                message="The file asset version was not found.",
            )
        return record

    def _validate_artifact_source(
        self,
        slot: ProjectAssetSlot,
        source_artifact_version_id: UUID | None,
    ) -> None:
        if source_artifact_version_id is None:
            return
        record = self._repository.get_artifact_version(source_artifact_version_id)
        if record is None:
            raise ApiError(
                status_code=404,
                code="ARTIFACT_VERSION_NOT_FOUND",
                message="The source artifact version was not found.",
            )
        _, artifact = record
        if artifact.project_id != slot.project_id or artifact.lesson_unit_id != slot.lesson_unit_id:
            raise ApiError(
                status_code=422,
                code="ASSET_SOURCE_MISMATCH",
                message="The source artifact does not match the target project and lesson.",
            )

    @staticmethod
    def _validate_file(
        slot: ProjectAssetSlot,
        asset_kind: str,
        mime_type: str,
        scan_status: str,
    ) -> None:
        if asset_kind != slot.asset_type:
            raise ApiError(
                status_code=422,
                code="ASSET_TYPE_MISMATCH",
                message="The file asset type does not match the slot contract.",
            )
        contract = AssetTargetContract.model_validate(slot.target_contract_json)
        if contract.require_clean_scan and scan_status != "clean":
            raise ApiError(
                status_code=422,
                code="ASSET_SCAN_REQUIRED",
                message="The file asset version has not passed required scanning.",
            )
        if contract.allowed_mime_types and not any(
            ProjectAssetService._mime_matches(pattern, mime_type)
            for pattern in contract.allowed_mime_types
        ):
            raise ApiError(
                status_code=422,
                code="ASSET_CONTRACT_MISMATCH",
                message="The file MIME type does not match the slot contract.",
            )

    @staticmethod
    def _mime_matches(pattern: str, mime_type: str) -> bool:
        if pattern.endswith("/*"):
            return mime_type.startswith(pattern[:-1])
        return pattern == mime_type

    def _resolve_position(
        self,
        slot: ProjectAssetSlot,
        active: list[AssetBinding],
        *,
        replace_mode: ReplaceMode,
        position: int | None,
    ) -> tuple[int, AssetBinding | None]:
        if AssetCardinality(slot.cardinality) == AssetCardinality.ONE:
            if position not in {None, 0} or replace_mode == ReplaceMode.APPEND:
                raise self._invalid_position()
            occupied = active[0] if active else None
            if occupied is not None and replace_mode == ReplaceMode.REJECT_IF_OCCUPIED:
                raise ApiError(
                    status_code=409,
                    code="ASSET_SLOT_OCCUPIED",
                    message="The single-value asset slot already has an active binding.",
                )
            if occupied is None and replace_mode == ReplaceMode.REPLACE_ACTIVE:
                raise ApiError(
                    status_code=409,
                    code="ASSET_SLOT_EMPTY",
                    message="The single-value asset slot has no active binding to replace.",
                )
            return 0, occupied

        if replace_mode == ReplaceMode.APPEND:
            resolved = (
                position
                if position is not None
                else max((binding.position for binding in active), default=0) + 1
            )
            if resolved <= 0:
                raise self._invalid_position()
            if any(binding.position == resolved for binding in active):
                raise self._position_occupied()
            return resolved, None
        if position is None or position <= 0:
            raise self._invalid_position()
        occupied = next((binding for binding in active if binding.position == position), None)
        if replace_mode == ReplaceMode.REJECT_IF_OCCUPIED:
            if occupied is not None:
                raise self._position_occupied()
            return position, None
        if occupied is None:
            raise ApiError(
                status_code=409,
                code="ASSET_POSITION_EMPTY",
                message="The requested asset position has no active binding to replace.",
            )
        return position, occupied

    def _deactivate(self, binding: AssetBinding, *, now: datetime) -> None:
        binding.is_active = False
        binding.unbound_at = now
        binding.unbound_by = self._actor.principal_id

    def _touch_slot(self, slot: ProjectAssetSlot, *, status: str, now: datetime) -> None:
        slot.status = status
        slot.lock_version += 1
        slot.updated_at = now
        slot.updated_by = self._actor.principal_id

    @staticmethod
    def _slot_not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="ASSET_SLOT_NOT_FOUND",
            message="The project asset slot was not found.",
        )

    @staticmethod
    def _binding_not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="ASSET_BINDING_NOT_FOUND",
            message="The project asset binding was not found.",
        )

    @staticmethod
    def _invalid_position() -> ApiError:
        return ApiError(
            status_code=422,
            code="ASSET_POSITION_INVALID",
            message="The binding position is invalid for the slot cardinality and replace mode.",
        )

    @staticmethod
    def _position_occupied() -> ApiError:
        return ApiError(
            status_code=409,
            code="ASSET_POSITION_OCCUPIED",
            message="The requested asset position already has an active binding.",
        )
