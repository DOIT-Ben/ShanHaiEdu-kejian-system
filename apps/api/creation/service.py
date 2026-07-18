"""Creation batch, prompt, generation, and adoption commands."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.assets.repository import FileAssetRepository
from apps.api.creation.models import (
    Adoption,
    CreationBatch,
    CreationPromptVersion,
)
from apps.api.creation.presenters import present_adoption, present_prompt
from apps.api.creation.repository import CreationRepository
from apps.api.creation.schemas import (
    AdoptGenerationResultRequest,
    AdoptionRead,
    CreateCreationBatchRequest,
    GenerateCreationBatchRequest,
    GenerateCreationItemRequest,
    LegacyGenerateCreationBatchRequest,
    ProjectCreationBatchRead,
    PromptVersionRead,
    SaveAdoptionToProjectRequest,
    SavePromptVersionRequest,
    SaveToProjectOperationRead,
    StandaloneCreationBatchRead,
)
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.jobs.schemas import AcceptedJobData
from apps.api.reliability.events import EventResource, EventWriter, append_outbox_only
from apps.api.reliability.idempotency import (
    CommandResult,
    IdempotencyService,
    canonical_request_hash,
)


class CreationService:
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
        self._idempotency_ttl_seconds = idempotency_ttl_seconds
        self._idempotency = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=idempotency_ttl_seconds,
        )

    def create_batch(
        self,
        payload: CreateCreationBatchRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> ProjectCreationBatchRead | StandaloneCreationBatchRead:
        from apps.api.creation.batch_service import CreationBatchService

        return CreationBatchService(
            self._session,
            self._actor,
            idempotency_ttl_seconds=self._idempotency_ttl_seconds,
        ).create(payload, idempotency_key=idempotency_key, request_id=request_id)

    def save_prompt_version(
        self,
        item_id: UUID,
        payload: SavePromptVersionRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> PromptVersionRead:
        request_payload = payload.model_dump(mode="json")

        def command() -> CommandResult:
            context = self._require_item(item_id, ProjectAction.GENERATE, for_update=True)
            self._validate_reference_assets(payload.reference_asset_version_ids)
            version = CreationPromptVersion(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                creation_item_id=context.item.id,
                version_no=self._repository.next_prompt_version(context.item.id),
                business_prompt=payload.business_prompt,
                reference_asset_version_ids=[
                    str(value) for value in payload.reference_asset_version_ids
                ],
                output_spec_json=payload.output_spec,
                generation_profile=payload.generation_profile,
                content_hash=canonical_request_hash(request_payload),
                created_at=utc_now(),
                created_by=self._actor.principal_id,
            )
            self._session.add(version)
            self._session.flush()
            context.item.current_prompt_version_id = version.id
            context.item.status = "ready"
            context.item.lock_version += 1
            context.item.updated_by = self._actor.principal_id
            self._session.flush()
            self._append_project_event(
                context.batch,
                event_type="creation.prompt_version.saved",
                resource=EventResource(type="prompt_version", id=version.id),
                payload={
                    "creation_item_id": str(context.item.id),
                    "prompt_version_id": str(version.id),
                    "version_no": version.version_no,
                },
                request_id=request_id,
            )
            return CommandResult(
                201,
                present_prompt(version).model_dump(mode="json"),
                "prompt_version",
                version.id,
            )

        result = self._idempotency.execute(
            scope=f"creation_prompt_versions.save:{item_id}",
            key=idempotency_key,
            payload=request_payload,
            command=command,
        )
        return PromptVersionRead.model_validate(result.body)

    def generate_item(
        self,
        item_id: UUID,
        payload: GenerateCreationItemRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> AcceptedJobData:
        from apps.api.creation.generation_service import CreationGenerationService

        return CreationGenerationService(
            self._session,
            self._actor,
            idempotency_ttl_seconds=self._idempotency_ttl_seconds,
        ).generate_item(
            item_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )

    def generate_batch(
        self,
        batch_id: UUID,
        payload: GenerateCreationBatchRequest | LegacyGenerateCreationBatchRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> AcceptedJobData:
        from apps.api.creation.generation_service import CreationGenerationService

        return CreationGenerationService(
            self._session,
            self._actor,
            idempotency_ttl_seconds=self._idempotency_ttl_seconds,
        ).generate_batch(
            batch_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )

    def adopt_result(
        self,
        result_id: UUID,
        payload: AdoptGenerationResultRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> AdoptionRead:
        def command() -> CommandResult:
            context = self._repository.get_result_context(result_id, for_update=True)
            if context is None or context.result.status != "available":
                raise ApiError(
                    status_code=404,
                    code="GENERATION_RESULT_NOT_FOUND",
                    message="The generation result was not found.",
                )
            self._authorize_batch(context.batch, ProjectAction.GENERATE)
            adoption = Adoption(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                creation_item_id=context.item.id,
                generation_result_id=context.result.id,
                adoption_mode="teacher",
                reason=payload.reason,
                adopted_at=utc_now(),
                adopted_by=self._actor.principal_id,
            )
            self._session.add(adoption)
            self._session.flush()
            context.item.active_adoption_id = adoption.id
            context.item.status = "adopted"
            context.item.lock_version += 1
            context.item.updated_by = self._actor.principal_id
            self._session.flush()
            self._append_project_event(
                context.batch,
                event_type="creation.candidate.adopted",
                resource=EventResource(type="adoption", id=adoption.id),
                payload={
                    "creation_item_id": str(context.item.id),
                    "generation_result_id": str(context.result.id),
                    "adoption_mode": adoption.adoption_mode,
                },
                request_id=request_id,
            )
            return CommandResult(
                201,
                present_adoption(adoption).model_dump(mode="json"),
                "adoption",
                adoption.id,
            )

        result = self._idempotency.execute(
            scope=f"creation_results.adopt:{result_id}",
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            command=command,
        )
        return AdoptionRead.model_validate(result.body)

    def save_adoption(
        self,
        adoption_id: UUID,
        payload: SaveAdoptionToProjectRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> SaveToProjectOperationRead:
        from apps.api.creation.save_service import CreationSaveService

        return CreationSaveService(
            self._session,
            self._actor,
            idempotency_ttl_seconds=self._idempotency_ttl_seconds,
        ).save(
            adoption_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )

    def resolve_save_target(
        self,
        batch_id: UUID,
        payload: SaveAdoptionToProjectRequest,
    ) -> tuple[UUID, str]:
        from apps.api.creation.save_service import CreationSaveService

        batch = self._repository.get_batch(batch_id)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="CREATION_BATCH_NOT_FOUND",
                message="The creation batch was not found.",
            )
        return CreationSaveService(
            self._session,
            self._actor,
            idempotency_ttl_seconds=self._idempotency_ttl_seconds,
        ).resolve_target(batch, None, payload)

    def _require_item(self, item_id: UUID, action: ProjectAction, *, for_update: bool = False):
        context = self._repository.get_item_context(item_id, for_update=for_update)
        if context is None:
            raise ApiError(
                status_code=404,
                code="CREATION_ITEM_NOT_FOUND",
                message="The creation item was not found.",
            )
        self._authorize_batch(context.batch, action)
        return context

    def _authorize_batch(self, batch: CreationBatch, action: ProjectAction) -> None:
        if batch.source_project_id is not None:
            ProjectAccessService(self._session, self._actor).require(
                batch.source_project_id,
                action,
            )
        elif self._actor.user_id is None or self._actor.is_system:
            raise ApiError(status_code=403, code="PERMISSION_DENIED", message="Access denied.")

    def _validate_reference_assets(self, version_ids: list[UUID]) -> None:
        repository = FileAssetRepository(self._session, self._actor)
        if any(repository.get_file_version(version_id) is None for version_id in set(version_ids)):
            raise ApiError(
                status_code=404,
                code="FILE_ASSET_VERSION_NOT_FOUND",
                message="A referenced file asset version was not found.",
            )

    def _append_project_event(
        self,
        batch: CreationBatch,
        *,
        event_type: str,
        resource: EventResource,
        payload: dict[str, object],
        request_id: str,
    ) -> None:
        if batch.source_project_id is not None:
            EventWriter(self._session, self._actor.organization_id).append(
                project_id=batch.source_project_id,
                event_type=event_type,
                resource=resource,
                payload=payload,
                request_id=request_id,
            )
        else:
            append_outbox_only(
                self._session,
                self._actor.organization_id,
                event_type=event_type,
                resource=resource,
                payload=payload,
                request_id=request_id,
            )
