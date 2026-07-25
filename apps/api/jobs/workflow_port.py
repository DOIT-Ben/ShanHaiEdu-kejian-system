"""Jobs-owned enqueue capability for exact lesson-plan NodeRuns."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.repository import GenerationJobRepository


class LessonPlanGenerationJobPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = GenerationJobRepository(session, actor.organization_id)

    def has_active(self, node_run_id: UUID) -> bool:
        return self._repository.active_for_node(node_run_id, for_update=True) is not None

    def enqueue(
        self,
        *,
        project_id: UUID,
        node_run_id: UUID,
        lesson_unit_id: UUID,
        workflow_node_key: str,
        creation_request: dict[str, object],
        idempotency_key: str,
        request_hash: str,
    ) -> UUID:
        job = GenerationJob(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=project_id,
            source_material_id=None,
            node_run_id=node_run_id,
            lesson_unit_id=lesson_unit_id,
            workflow_node_key=workflow_node_key,
            result_artifact_version_id=None,
            creation_prompt_version_id=None,
            creation_batch_id=None,
            creation_request_json=creation_request,
            job_type="workflow.node",
            status="queued",
            progress_percent=0,
            progress_message="Queued for lesson-plan generation",
            error_code=None,
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
