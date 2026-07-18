"""Atomic adoption-to-project save command."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.assets.project_contracts import ReplaceMode
from apps.api.assets.project_repository import ProjectAssetRepository
from apps.api.assets.project_service import ProjectAssetService
from apps.api.creation.access import CreationBatchAccessService
from apps.api.creation.models import CreationBatch, CreationItem, SaveToProjectOperation
from apps.api.creation.repository import CreationRepository
from apps.api.creation.schemas import (
    ProjectSourceSaveRequest,
    SaveAdoptionToProjectRequest,
    SaveToProjectOperationRead,
    StandaloneSourceSaveRequest,
)
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.idempotency import CommandResult, IdempotencyService


class CreationSaveService:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        idempotency_ttl_seconds: int,
    ) -> None:
        self._session = session
        self._actor = actor
        self._repository = CreationRepository(session, actor.organization_id)
        self._idempotency = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=idempotency_ttl_seconds,
        )

    def save(
        self,
        adoption_id: UUID,
        payload: SaveAdoptionToProjectRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> SaveToProjectOperationRead:
        request_payload = payload.model_dump(mode="json")
        current = self._repository.get_adoption_context(adoption_id)
        if current is None or current.item.active_adoption_id != adoption_id:
            raise ApiError(
                status_code=409,
                code="CANDIDATE_NOT_ADOPTED",
                message="The candidate is not the active adoption for this item.",
            )
        CreationBatchAccessService(self._session, self._actor).require(
            current.batch,
            ProjectAction.EDIT,
        )

        def command() -> CommandResult:
            context = self._repository.get_adoption_context(adoption_id, for_update=True)
            if context is None or context.item.active_adoption_id != adoption_id:
                raise ApiError(
                    status_code=409,
                    code="CANDIDATE_NOT_ADOPTED",
                    message="The candidate is not the active adoption for this item.",
                )
            CreationBatchAccessService(self._session, self._actor).require(
                context.batch,
                ProjectAction.EDIT,
                for_update=True,
            )
            if context.result.file_asset_version_id is None:
                raise ApiError(
                    status_code=409,
                    code="CANDIDATE_NOT_ADOPTED",
                    message="The adopted candidate has no savable file asset.",
                )
            target_project_id, target_slot_key = self.resolve_target(
                context.batch,
                context.item,
                payload,
            )
            slot = ProjectAssetRepository(self._session, self._actor).get_slot_by_key(
                target_project_id,
                target_slot_key,
                for_update=True,
            )
            if slot is None:
                raise self._target_forbidden()
            operation = SaveToProjectOperation(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                idempotency_key=idempotency_key,
                source_adoption_id=adoption_id,
                target_project_id=target_project_id,
                target_slot_key=target_slot_key,
                replace_mode=payload.replace_mode,
                authorization_snapshot_json={
                    "principal_id": str(self._actor.principal_id),
                    "project_id": str(target_project_id),
                    "action": ProjectAction.EDIT.value,
                },
                status="pending",
                created_binding_id=None,
                completed_at=None,
                created_at=utc_now(),
                created_by=self._actor.principal_id,
            )
            self._session.add(operation)
            self._session.flush()
            binding = ProjectAssetService(self._session, self._actor).bind(
                slot.id,
                file_asset_version_id=context.result.file_asset_version_id,
                source_artifact_version_id=None,
                source_generation_result_id=context.result.id,
                save_operation_id=operation.id,
                replace_mode=ReplaceMode(payload.replace_mode),
                position=None,
                request_id=request_id,
            )
            operation.status = "completed"
            operation.created_binding_id = binding.id
            operation.completed_at = utc_now()
            context.item.status = "saved"
            context.item.lock_version += 1
            context.item.updated_by = self._actor.principal_id
            self._session.flush()
            EventWriter(self._session, self._actor.organization_id).append(
                project_id=target_project_id,
                event_type="creation.project_save.completed",
                resource=EventResource(type="save_to_project_operation", id=operation.id),
                payload={
                    "adoption_id": str(adoption_id),
                    "binding_id": str(binding.id),
                    "target_project_id": str(target_project_id),
                    "target_slot_key": target_slot_key,
                },
                request_id=request_id,
            )
            body = SaveToProjectOperationRead(
                operation_id=operation.id,
                adoption_id=adoption_id,
                status="completed",
                binding_id=binding.id,
                target_project_id=target_project_id,
                target_slot_key=target_slot_key,
                idempotent_replay=False,
            ).model_dump(mode="json")
            return CommandResult(200, body, "save_to_project_operation", operation.id)

        result = self._idempotency.execute(
            scope=f"creation_adoptions.save:{adoption_id}",
            key=idempotency_key,
            payload=request_payload,
            authorize=lambda: self._require_save_access(adoption_id, payload),
            command=command,
        )
        body = dict(result.body)
        body["idempotent_replay"] = result.replayed
        return SaveToProjectOperationRead.model_validate(body)

    def _require_save_access(
        self,
        adoption_id: UUID,
        payload: SaveAdoptionToProjectRequest,
    ) -> None:
        context = self._repository.get_adoption_context(adoption_id, for_update=True)
        if context is None:
            raise ApiError(
                status_code=409,
                code="CANDIDATE_NOT_ADOPTED",
                message="The candidate is not the active adoption for this item.",
            )
        CreationBatchAccessService(self._session, self._actor).require(
            context.batch,
            ProjectAction.EDIT,
            for_update=True,
        )
        if isinstance(payload, StandaloneSourceSaveRequest):
            try:
                ProjectAccessService(self._session, self._actor).require(
                    payload.project_id,
                    ProjectAction.EDIT,
                    for_update=True,
                )
            except ApiError as exc:
                raise self._target_forbidden() from exc

    def resolve_target(
        self,
        batch: CreationBatch,
        item: CreationItem | None,
        payload: SaveAdoptionToProjectRequest,
    ) -> tuple[UUID, str]:
        if batch.source_kind != payload.source_kind:
            raise ApiError(
                status_code=422,
                code="CREATION_SOURCE_MISMATCH",
                message="The save request source does not match the creation batch.",
            )
        if isinstance(payload, ProjectSourceSaveRequest):
            if batch.source_project_id is None or item is None or item.target_slot_key is None:
                raise ApiError(
                    status_code=422,
                    code="TARGET_OVERRIDE_FORBIDDEN",
                    message="Project creation must use the immutable package target.",
                )
            package = (
                self._repository.get_package(batch.creation_package_id)
                if batch.creation_package_id is not None
                else None
            )
            raw_modes: object = (
                cast(object, package.target_rules_json.get("replace_modes", []))
                if package is not None
                else []
            )
            allowed_modes = (
                [value for value in cast(list[object], raw_modes) if isinstance(value, str)]
                if isinstance(raw_modes, list)
                else []
            )
            if payload.replace_mode not in allowed_modes:
                raise ApiError(
                    status_code=422,
                    code="TARGET_OVERRIDE_FORBIDDEN",
                    message="The replace mode is outside the immutable package save scope.",
                )
            ProjectAccessService(self._session, self._actor).require(
                batch.source_project_id,
                ProjectAction.EDIT,
                for_update=True,
            )
            return batch.source_project_id, item.target_slot_key
        try:
            ProjectAccessService(self._session, self._actor).require(
                payload.project_id,
                ProjectAction.EDIT,
                for_update=True,
            )
        except ApiError as exc:
            raise self._target_forbidden() from exc
        slot = ProjectAssetRepository(self._session, self._actor).get_slot_by_key(
            payload.project_id,
            payload.slot_key,
        )
        if slot is None:
            raise self._target_forbidden()
        return payload.project_id, payload.slot_key

    @staticmethod
    def _target_forbidden() -> ApiError:
        return ApiError(
            status_code=404,
            code="PROJECT_TARGET_FORBIDDEN",
            message="The target project or asset slot is unavailable.",
        )
