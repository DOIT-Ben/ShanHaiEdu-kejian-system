"""Creation item and batch generation job commands."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.creation.access import CreationBatchAccessService
from apps.api.creation.models import CreationBatch
from apps.api.creation.repository import CreationRepository
from apps.api.creation.schemas import (
    GenerateCreationBatchRequest,
    GenerateCreationItemRequest,
    LegacyGenerateCreationBatchRequest,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.schemas import AcceptedJobData
from apps.api.reliability.events import EventResource, EventWriter, append_outbox_only
from apps.api.reliability.idempotency import (
    CommandResult,
    IdempotencyService,
    canonical_request_hash,
)


class CreationGenerationService:
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

    def generate_item(
        self,
        item_id: UUID,
        payload: GenerateCreationItemRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> AcceptedJobData:
        context = self._require_item(item_id)
        return self._enqueue(
            batch=context.batch,
            prompt_version_id=payload.prompt_version_id,
            batch_id=None,
            creation_request=payload.model_dump(mode="json"),
            item_id=item_id,
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
        batch = self._require_batch(batch_id)
        items = {item.id: item for item in self._repository.batch_items(batch.id)}
        requested: list[dict[str, object]]
        if isinstance(payload, LegacyGenerateCreationBatchRequest):
            requested = []
            for item_id in payload.item_ids:
                item = items.get(item_id)
                if item is None or item.current_prompt_version_id is None:
                    raise self._prompt_stale()
                requested.append(
                    {
                        "item_id": item_id,
                        "prompt_version_id": item.current_prompt_version_id,
                        "candidate_count": 1,
                    }
                )
        else:
            requested = [item.model_dump(mode="python") for item in payload.items]
        for entry in requested:
            item_id_value = entry.get("item_id")
            prompt_id_value = entry.get("prompt_version_id")
            if not isinstance(item_id_value, UUID) or not isinstance(prompt_id_value, UUID):
                raise self._prompt_stale()
            item = items.get(item_id_value)
            if item is None or item.current_prompt_version_id != prompt_id_value:
                raise self._prompt_stale()
        return self._enqueue(
            batch=batch,
            prompt_version_id=None,
            batch_id=batch.id,
            creation_request={
                "items": [
                    {
                        key: str(value) if isinstance(value, UUID) else value
                        for key, value in item.items()
                    }
                    for item in requested
                ]
            },
            item_id=None,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )

    def _enqueue(
        self,
        *,
        batch: CreationBatch,
        prompt_version_id: UUID | None,
        batch_id: UUID | None,
        creation_request: dict[str, object],
        item_id: UUID | None,
        idempotency_key: str,
        request_id: str,
    ) -> AcceptedJobData:
        if prompt_version_id is not None:
            prompt = self._repository.get_prompt_version(prompt_version_id)
            item_context = (
                self._repository.get_item_context(item_id) if item_id is not None else None
            )
            if (
                prompt is None
                or prompt.creation_item_id != item_id
                or item_context is None
                or item_context.item.current_prompt_version_id != prompt.id
            ):
                raise self._prompt_stale()

        def command() -> CommandResult:
            job = GenerationJob(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                project_id=batch.source_project_id,
                source_material_id=None,
                creation_prompt_version_id=prompt_version_id,
                creation_batch_id=batch_id,
                creation_request_json=creation_request,
                job_type="creation.item" if prompt_version_id is not None else "creation.batch",
                status="queued",
                progress_percent=0,
                progress_message="Queued for creation",
                error_code=None,
                idempotency_key=idempotency_key,
                request_hash=canonical_request_hash(creation_request),
                priority=100,
                attempt_count=0,
                created_by=self._actor.principal_id,
                updated_by=self._actor.principal_id,
            )
            self._session.add(job)
            self._session.flush()
            resource = EventResource(type="generation_job", id=job.id)
            event_payload = {"status": "queued", "progress_percent": 0, "attempt_count": 0}
            if batch.source_project_id is not None:
                EventWriter(self._session, self._actor.organization_id).append(
                    project_id=batch.source_project_id,
                    event_type="generation.job.queued",
                    resource=resource,
                    payload=event_payload,
                    request_id=request_id,
                )
            else:
                append_outbox_only(
                    self._session,
                    self._actor.organization_id,
                    event_type="generation.job.queued",
                    resource=resource,
                    payload=event_payload,
                    request_id=request_id,
                )
            body = AcceptedJobData(
                job_id=job.id,
                status="queued",
                events_url=f"/api/v2/generation-jobs/{job.id}/events/stream",
            ).model_dump(mode="json")
            return CommandResult(202, body, "generation_job", job.id)

        result = self._idempotency.execute(
            scope=f"creation.generate:{batch.id}:{item_id or 'batch'}",
            key=idempotency_key,
            payload=creation_request,
            command=command,
        )
        return AcceptedJobData.model_validate(result.body)

    def _require_item(self, item_id: UUID):
        context = self._repository.get_item_context(item_id)
        if context is None:
            raise ApiError(
                status_code=404,
                code="CREATION_ITEM_NOT_FOUND",
                message="The creation item was not found.",
            )
        self._authorize_batch(context.batch)
        return context

    def _require_batch(self, batch_id: UUID) -> CreationBatch:
        batch = self._repository.get_batch(batch_id)
        if batch is None:
            raise ApiError(
                status_code=404,
                code="CREATION_BATCH_NOT_FOUND",
                message="The creation batch was not found.",
            )
        self._authorize_batch(batch)
        return batch

    def _authorize_batch(self, batch: CreationBatch) -> None:
        CreationBatchAccessService(self._session, self._actor).require(
            batch,
            ProjectAction.GENERATE,
        )

    @staticmethod
    def _prompt_stale() -> ApiError:
        return ApiError(
            status_code=409,
            code="PROMPT_VERSION_STALE",
            message="The prompt version is not the current version for this creation item.",
        )
