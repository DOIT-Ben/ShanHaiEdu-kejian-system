"""Transactional command that queues one prepared model-generation NodeRun."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.content_runtime.runtime_port import (
    RuntimeDefinitionError,
    SqlAlchemyRuntimeDefinitionReader,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.repository import GenerationJobRepository
from apps.api.jobs.schemas import AcceptedJobData
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.idempotency import (
    CommandResult,
    IdempotencyService,
    canonical_request_hash,
)
from apps.api.workflows.execution_port import (
    SqlAlchemyWorkflowExecutionPort,
    WorkflowExecutionPortError,
)
from apps.api.workflows.schemas import StartNodeRunRequest
from workflow.node_state import NodeStatus


class NodeRunStartService:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        idempotency_ttl_seconds: int,
    ) -> None:
        self._session = session
        self._actor = actor
        self._workflow = SqlAlchemyWorkflowExecutionPort(session, actor)
        self._definitions = SqlAlchemyRuntimeDefinitionReader(
            session,
            actor,
            self._workflow,
        )
        self._jobs = GenerationJobRepository(session, actor.organization_id)
        self._idempotency = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=idempotency_ttl_seconds,
        )

    def start(
        self,
        node_run_id: UUID,
        payload: StartNodeRunRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> AcceptedJobData:
        request_payload = payload.model_dump(mode="json", exclude_none=True)

        def command() -> CommandResult:
            execution = self._require_execution(node_run_id, for_update=True)
            if execution.status != NodeStatus.READY.value:
                raise ApiError(
                    status_code=409,
                    code="NODE_RUN_NOT_READY",
                    message="The node run is not ready to start.",
                )
            self._require_model_generation(node_run_id)
            if self._jobs.active_for_node(node_run_id, for_update=True) is not None:
                raise ApiError(
                    status_code=409,
                    code="NODE_RUN_JOB_ACTIVE",
                    message="The node run already has an active generation job.",
                )
            job = GenerationJob(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                project_id=execution.project_id,
                source_material_id=None,
                node_run_id=node_run_id,
                lesson_unit_id=execution.lesson_unit_id,
                result_artifact_version_id=None,
                creation_prompt_version_id=None,
                creation_batch_id=None,
                creation_request_json=request_payload,
                job_type="workflow.node",
                status="queued",
                progress_percent=0,
                progress_message="Queued for node execution",
                error_code=None,
                idempotency_key=idempotency_key,
                request_hash=canonical_request_hash(request_payload),
                priority=100,
                attempt_count=0,
                created_by=self._actor.principal_id,
                updated_by=self._actor.principal_id,
            )
            self._session.add(job)
            self._workflow.transition(node_run_id, NodeStatus.QUEUED)
            self._session.flush()
            EventWriter(self._session, self._actor.organization_id).append(
                project_id=execution.project_id,
                event_type="generation.job.queued",
                resource=EventResource(type="generation_job", id=job.id),
                payload={
                    "status": "queued",
                    "progress_percent": 0,
                    "attempt_count": 0,
                    "node_run_id": str(node_run_id),
                    "lesson_unit_id": (
                        str(execution.lesson_unit_id)
                        if execution.lesson_unit_id is not None
                        else None
                    ),
                },
                request_id=request_id,
            )
            body = AcceptedJobData(
                job_id=job.id,
                status="queued",
                events_url=f"/api/v2/generation-jobs/{job.id}/events/stream",
            ).model_dump(mode="json")
            return CommandResult(202, body, "generation_job", job.id)

        result = self._idempotency.execute(
            scope=f"node-runs.start:{node_run_id}:{self._actor.principal_id}",
            key=idempotency_key,
            payload=request_payload,
            authorize=lambda: self._require_execution(node_run_id, for_update=False),
            command=command,
        )
        return AcceptedJobData.model_validate(result.body)

    def _require_execution(self, node_run_id: UUID, *, for_update: bool):
        try:
            return self._workflow.require_context(node_run_id, for_update=for_update)
        except WorkflowExecutionPortError as exc:
            status_code = 404 if exc.code == "NODE_EXECUTION_NOT_FOUND" else 409
            raise ApiError(
                status_code=status_code,
                code=exc.code,
                message="The node run is unavailable for generation.",
            ) from exc

    def _require_model_generation(self, node_run_id: UUID) -> None:
        try:
            self._definitions.resolve(node_run_id)
        except RuntimeDefinitionError as exc:
            raise ApiError(
                status_code=409,
                code=exc.code,
                message="The node run does not support model generation.",
            ) from exc
