"""Jobs-owned enqueue capability for immutable material parse inputs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.repository import GenerationJobRepository


class MaterialParseJobPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = GenerationJobRepository(session, actor.organization_id)

    def has_active(self, source_material_id: UUID) -> bool:
        return (
            self._repository.active_material_parse(source_material_id, for_update=True) is not None
        )

    def enqueue(
        self,
        *,
        project_id: UUID,
        source_material_id: UUID,
        file_asset_version_id: UUID,
        idempotency_key: str,
        request_hash: str,
    ) -> UUID:
        job = GenerationJob(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=project_id,
            source_material_id=source_material_id,
            creation_request_json={"file_asset_version_id": str(file_asset_version_id)},
            job_type="material.parse",
            status="queued",
            progress_percent=0,
            progress_message="Material reparse queued",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            priority=100,
            attempt_count=0,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(job)
        self._session.flush()
        return job.id
