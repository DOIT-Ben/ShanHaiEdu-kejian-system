"""GenerationJob-backed execution for supported R1 generation nodes."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.execution_errors import ArtifactExecutionPortError
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, system_actor
from apps.api.identity.repository import IdentityRepository
from apps.api.jobs.service import GenerationJobService
from apps.api.jobs.worker_port import GenerationJobRouting, GenerationJobRoutingReader
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.factory import build_real_text_gateway
from apps.api.node_execution.contracts import NodeExecutionError, NodeExecutionModelPort
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.settings import Settings, get_settings
from apps.api.workflows.execution_port import (
    SqlAlchemyWorkflowExecutionPort,
    WorkflowExecutionPortError,
)
from workflow.node_state import NodeStatus

logger = logging.getLogger(__name__)


class NodeExecutionJobInFlight(RuntimeError):
    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__("node execution is owned by another worker")
        self.retry_after_seconds = retry_after_seconds


async def execute_node_execution_job(
    job_id: UUID,
    *,
    worker_id: str,
    model: NodeExecutionModelPort | None = None,
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    if resolved_settings.database_url is None:
        raise RuntimeError("worker database persistence is not configured")
    engine = build_engine(resolved_settings.database_url.get_secret_value())
    factory = build_session_factory(engine)
    try:
        return await _execute_job(
            factory,
            job_id,
            worker_id=worker_id,
            model=model,
            settings=resolved_settings,
        )
    finally:
        engine.dispose()


async def _execute_job(
    factory: sessionmaker[Session],
    job_id: UUID,
    *,
    worker_id: str,
    model: NodeExecutionModelPort | None,
    settings: Settings,
) -> str:
    routing = _job_facts(factory, job_id)
    if routing is None:
        return "ignored"
    worker_actor = system_actor(routing.organization_id)
    if not _claim_job(
        factory,
        worker_actor,
        job_id,
        node_run_id=routing.node_run_id,
        worker_id=worker_id,
        settings=settings,
    ):
        return (
            "cancelled"
            if _synchronize_cancelled_node(factory, job_id, routing.node_run_id)
            else "ignored"
        )
    return await _run_claimed_job(
        factory,
        routing,
        job_id=job_id,
        worker_id=worker_id,
        worker_actor=worker_actor,
        model=model,
        settings=settings,
    )


def _claim_job(
    factory: sessionmaker[Session],
    actor: ActorContext,
    job_id: UUID,
    *,
    node_run_id: UUID,
    worker_id: str,
    settings: Settings,
) -> bool:
    with factory() as session, session.begin():
        current = GenerationJobRoutingReader(session).get_supported_r1(job_id)
        if current is not None and current.status == "running":
            retry_after = SqlAlchemyWorkflowExecutionPort(
                session,
                actor,
            ).execution_retry_after_seconds(node_run_id)
            if retry_after is not None:
                raise NodeExecutionJobInFlight(retry_after_seconds=retry_after)
        claimed = GenerationJobService(
            session,
            actor=actor,
            idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
        ).claim(job_id, worker_id=worker_id, lease_seconds=settings.worker_lease_seconds)
        return claimed is not None


async def _run_claimed_job(
    factory: sessionmaker[Session],
    routing: GenerationJobRouting,
    *,
    job_id: UUID,
    worker_id: str,
    worker_actor: ActorContext,
    model: NodeExecutionModelPort | None,
    settings: Settings,
) -> str:
    initiating_actor = worker_actor
    try:
        initiating_actor = _initiating_actor(factory, routing)
        resolved_model = model or _real_model(factory, settings)
        result = await NodeExecutionService(
            SqlAlchemyNodeExecutionTransactionFactory(factory, initiating_actor),
            resolved_model,
            generation_job_id=job_id,
        ).execute(
            routing.node_run_id,
            request_id=f"generation-job:{job_id}",
            user_revision=_user_revision(routing.creation_request),
        )
    except (NodeExecutionError, ArtifactExecutionPortError) as exc:
        return _fail_node_execution(
            factory,
            initiating_actor,
            worker_actor,
            routing.node_run_id,
            job_id,
            worker_id=worker_id,
            settings=settings,
            code=exc.code,
        )
    except Exception:
        _fail_worker_execution(
            factory,
            worker_actor,
            routing.node_run_id,
            job_id,
            worker_id=worker_id,
            settings=settings,
        )
        raise
    status = _complete_job(
        factory,
        worker_actor,
        job_id,
        worker_id=worker_id,
        settings=settings,
        result_artifact_version_id=result.artifact_version_id,
    )
    return "succeeded" if status == "succeeded" else "ignored"


def _real_model(
    factory: sessionmaker[Session],
    settings: Settings,
) -> NodeExecutionModelPort:
    model, _provider = build_real_text_gateway(
        settings,
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    return model


def _job_facts(
    factory: sessionmaker[Session],
    job_id: UUID,
) -> GenerationJobRouting | None:
    with factory() as session:
        return GenerationJobRoutingReader(session).get_supported_r1(job_id)


def _initiating_actor(
    factory: sessionmaker[Session],
    routing: GenerationJobRouting,
) -> ActorContext:
    with factory() as session:
        return IdentityRepository(session).resolve_actor_for_principal(
            routing.created_by,
            routing.organization_id,
        )


def _fail_node_execution(
    factory: sessionmaker[Session],
    initiating_actor: ActorContext,
    worker_actor: ActorContext,
    node_run_id: UUID,
    job_id: UUID,
    *,
    worker_id: str,
    settings: Settings,
    code: str,
) -> str:
    _terminalize_node_failure(
        factory,
        initiating_actor,
        node_run_id,
        code=code,
        cancelled=code == "NODE_EXECUTION_CANCEL_REQUESTED",
    )
    status = _complete_job(
        factory,
        worker_actor,
        job_id,
        worker_id=worker_id,
        settings=settings,
        error_code=code,
    )
    return "cancelled" if status == "cancelled" else "failed"


def _fail_worker_execution(
    factory: sessionmaker[Session],
    worker_actor: ActorContext,
    node_run_id: UUID,
    job_id: UUID,
    *,
    worker_id: str,
    settings: Settings,
) -> None:
    code = "NODE_EXECUTION_WORKER_FAILED"
    logger.exception("node_generation_job_failed", extra={"job_id": str(job_id)})
    _terminalize_node_failure(
        factory,
        worker_actor,
        node_run_id,
        code=code,
        cancelled=False,
    )
    _complete_job(
        factory,
        worker_actor,
        job_id,
        worker_id=worker_id,
        settings=settings,
        error_code=code,
    )


def _user_revision(payload: dict[str, object] | None) -> str | None:
    if not payload or "user_revision" not in payload:
        return None
    value = payload["user_revision"]
    if not isinstance(value, str) or len(value) > 6_000:
        raise RuntimeError("node generation job contains an invalid user revision")
    return value


def _complete_job(
    factory: sessionmaker[Session],
    actor: ActorContext,
    job_id: UUID,
    *,
    worker_id: str,
    settings: Settings,
    error_code: str | None = None,
    result_artifact_version_id: UUID | None = None,
) -> str | None:
    with factory() as session, session.begin():
        completed = GenerationJobService(
            session,
            actor=actor,
            idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
        ).complete(
            job_id,
            worker_id=worker_id,
            error_code=error_code,
            result_artifact_version_id=result_artifact_version_id,
        )
        return completed.status if completed is not None else None


def _synchronize_cancelled_node(
    factory: sessionmaker[Session],
    job_id: UUID,
    node_run_id: UUID,
) -> bool:
    with factory() as session, session.begin():
        routing = GenerationJobRoutingReader(session).get_supported_r1(job_id)
        if routing is None or routing.status != "cancelled":
            return False
        actor = IdentityRepository(session).resolve_actor_for_principal(
            routing.created_by,
            routing.organization_id,
        )
        workflow = SqlAlchemyWorkflowExecutionPort(
            session,
            actor,
        )
        execution = workflow.require_context(node_run_id, for_update=True)
        node_status = NodeStatus(execution.status)
        if node_status is NodeStatus.CANCELLED:
            return True
        if node_status in {NodeStatus.QUEUED, NodeStatus.RUNNING}:
            workflow.transition(node_run_id, NodeStatus.CANCEL_REQUESTED)
            node_status = NodeStatus.CANCEL_REQUESTED
        if node_status is NodeStatus.CANCEL_REQUESTED:
            workflow.transition(node_run_id, NodeStatus.CANCELLED)
            return True
        raise RuntimeError("cancelled generation job is not aligned with its NodeRun")


def _terminalize_node_failure(
    factory: sessionmaker[Session],
    actor: ActorContext,
    node_run_id: UUID,
    *,
    code: str,
    cancelled: bool,
) -> None:
    try:
        with factory() as session, session.begin():
            workflow = SqlAlchemyWorkflowExecutionPort(session, actor)
            execution = workflow.require_context(node_run_id, for_update=True)
            if NodeStatus(execution.status) in {
                NodeStatus.FAILED,
                NodeStatus.CANCELLED,
                NodeStatus.REVIEW_REQUIRED,
                NodeStatus.APPROVED,
            }:
                return
            workflow.terminalize(
                node_run_id,
                code=code,
                cancelled=cancelled,
            )
    except (ApiError, WorkflowExecutionPortError):
        logger.exception(
            "node_generation_terminalization_failed",
            extra={"node_run_id": str(node_run_id)},
        )
