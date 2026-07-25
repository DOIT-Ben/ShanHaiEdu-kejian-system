"""Queue one prepared model-generation NodeRun as a GenerationJob."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.content_runtime.runtime_port import (
    RuntimeDefinitionError,
    SqlAlchemyRuntimeDefinitionReader,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.jobs.schemas import AcceptedJobData
from apps.api.jobs.workflow_port import LessonPlanGenerationJobPort
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
        self._definitions = SqlAlchemyRuntimeDefinitionReader(session, actor, self._workflow)
        self._jobs = LessonPlanGenerationJobPort(session, actor)
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
            return self._start_ready_node(
                node_run_id,
                request_payload=request_payload,
                idempotency_key=idempotency_key,
                request_id=request_id,
            )

        result = self._idempotency.execute(
            scope=f"node-runs.start:{node_run_id}:{self._actor.principal_id}",
            key=idempotency_key,
            payload=request_payload,
            authorize=lambda: self._require_execution(node_run_id, for_update=False),
            command=command,
        )
        return AcceptedJobData.model_validate(result.body)

    def _start_ready_node(
        self,
        node_run_id: UUID,
        *,
        request_payload: dict[str, object],
        idempotency_key: str,
        request_id: str,
    ) -> CommandResult:
        execution = self._require_execution(node_run_id, for_update=True)
        if execution.status != NodeStatus.READY.value:
            raise ApiError(
                status_code=409,
                code="NODE_RUN_NOT_READY",
                message="The node run is not ready to start.",
            )
        self._require_supported_generation(
            node_run_id,
            execution.node_key,
            execution.lesson_unit_id,
        )
        if self._jobs.has_active(node_run_id):
            raise ApiError(
                status_code=409,
                code="NODE_RUN_JOB_ACTIVE",
                message="The node run already has an active generation job.",
            )
        job_id = self._jobs.enqueue(
            project_id=execution.project_id,
            node_run_id=node_run_id,
            lesson_unit_id=execution.lesson_unit_id,
            workflow_node_key=execution.node_key,
            creation_request=request_payload,
            idempotency_key=idempotency_key,
            request_hash=canonical_request_hash(request_payload),
        )
        self._workflow.transition(node_run_id, NodeStatus.QUEUED)
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=execution.project_id,
            event_type="generation.job.queued",
            resource=EventResource(type="generation_job", id=job_id),
            payload={
                "status": "queued",
                "progress_percent": 0,
                "attempt_count": 0,
                "node_run_id": str(node_run_id),
                "lesson_unit_id": (
                    str(execution.lesson_unit_id) if execution.lesson_unit_id is not None else None
                ),
                "workflow_node_key": execution.node_key,
            },
            request_id=request_id,
        )
        body = AcceptedJobData(
            job_id=job_id,
            status="queued",
            events_url=f"/api/v2/generation-jobs/{job_id}/events/stream",
        ).model_dump(mode="json")
        return CommandResult(202, body, "generation_job", job_id)

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

    def _require_supported_generation(
        self,
        node_run_id: UUID,
        node_key: str,
        lesson_unit_id: UUID | None,
    ) -> None:
        supported = (node_key == "lesson_plan.generate" and lesson_unit_id is not None) or (
            node_key == "lesson.division.generate" and lesson_unit_id is None
        )
        if not supported:
            raise ApiError(
                status_code=409,
                code="NODE_RUN_UNSUPPORTED",
                message="The node run is outside the active R1 generation surface.",
            )
        try:
            self._definitions.resolve(node_run_id)
        except RuntimeDefinitionError as exc:
            raise ApiError(
                status_code=409,
                code=exc.code,
                message="The node run does not support model generation.",
            ) from exc
