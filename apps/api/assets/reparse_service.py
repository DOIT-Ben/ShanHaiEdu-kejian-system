"""Create one new parse job for the exact latest failed material input."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.assets.repository import FileAssetRepository
from apps.api.assets.schemas import RetryMaterialParseRequest
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.jobs.material_parse_port import MaterialParseJobPort
from apps.api.jobs.schemas import AcceptedJobData
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.idempotency import (
    CommandResult,
    IdempotencyService,
    canonical_request_hash,
)


class MaterialReparseService:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        idempotency_ttl_seconds: int,
    ) -> None:
        self._session = session
        self._actor = actor
        self._repository = FileAssetRepository(session, actor)
        self._jobs = MaterialParseJobPort(session, actor)
        self._idempotency = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=idempotency_ttl_seconds,
        )

    def retry(
        self,
        project_id: UUID,
        material_id: UUID,
        payload: RetryMaterialParseRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> AcceptedJobData:
        request_payload = payload.model_dump(mode="json")
        result = self._idempotency.execute(
            scope=f"material-parses.retry:{project_id}:{material_id}",
            key=idempotency_key,
            payload=request_payload,
            authorize=lambda: ProjectAccessService(self._session, self._actor).require(
                project_id,
                ProjectAction.GENERATE,
                for_update=True,
            ),
            command=lambda: self._retry_command(
                project_id,
                material_id,
                payload,
                idempotency_key=idempotency_key,
                request_id=request_id,
            ),
        )
        return AcceptedJobData.model_validate(result.body)

    def _retry_command(
        self,
        project_id: UUID,
        material_id: UUID,
        payload: RetryMaterialParseRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> CommandResult:
        self._require_retryable(project_id, material_id, payload.file_asset_version_id)
        request_payload = payload.model_dump(mode="json")
        job_id = self._jobs.enqueue(
            project_id=project_id,
            source_material_id=material_id,
            file_asset_version_id=payload.file_asset_version_id,
            idempotency_key=idempotency_key,
            request_hash=canonical_request_hash(request_payload),
        )
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=project_id,
            event_type="generation.job.queued",
            resource=EventResource(type="generation_job", id=job_id),
            payload={"status": "queued", "job_type": "material.parse"},
            request_id=request_id,
        )
        accepted = AcceptedJobData(
            job_id=job_id,
            status="queued",
            events_url=f"/api/v2/generation-jobs/{job_id}/events/stream",
        )
        return CommandResult(
            status_code=202,
            body=accepted.model_dump(mode="json"),
            resource_type="generation_job",
            resource_id=job_id,
        )

    def _require_retryable(
        self,
        project_id: UUID,
        material_id: UUID,
        file_asset_version_id: UUID,
    ) -> None:
        record = self._repository.get_for_material(project_id, material_id, for_update=True)
        if record is None:
            raise ApiError(
                status_code=404,
                code="MATERIAL_FILE_NOT_FOUND",
                message="The source material file was not found.",
            )
        if record.current_version.id != file_asset_version_id:
            raise ApiError(
                status_code=409,
                code="MATERIAL_FILE_VERSION_MISMATCH",
                message="The requested file version is not the material's current version.",
            )
        if self._jobs.has_active(material_id):
            raise ApiError(
                status_code=409,
                code="MATERIAL_PARSE_ALREADY_ACTIVE",
                message="The material already has an active parse job.",
            )
        parses = self._repository.list_parse_versions(project_id, material_id)
        latest = parses[0] if parses else None
        if (
            latest is None
            or latest.file_asset_version_id != file_asset_version_id
            or latest.status != "failed"
        ):
            raise ApiError(
                status_code=409,
                code="MATERIAL_PARSE_RETRY_NOT_ALLOWED",
                message="Only the exact latest failed material parse can be retried.",
            )
