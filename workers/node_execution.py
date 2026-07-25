"""GenerationJob-backed execution for prepared workflow nodes."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, AuthenticatedIdentity, system_actor
from apps.api.identity.models import Principal
from apps.api.identity.repository import IdentityRepository
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.service import GenerationJobService
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
        job_facts = _job_facts(factory, job_id)
        if job_facts is None:
            return "ignored"
        organization_id, node_run_id = job_facts
        worker_actor = system_actor(organization_id)
        with factory() as session, session.begin():
            claimed = GenerationJobService(
                session,
                actor=worker_actor,
                idempotency_ttl_seconds=resolved_settings.idempotency_ttl_seconds,
            ).claim(
                job_id,
                worker_id=worker_id,
                lease_seconds=resolved_settings.worker_lease_seconds,
            )
        if claimed is None:
            return (
                "cancelled"
                if _synchronize_cancelled_node(factory, job_id, node_run_id)
                else "ignored"
            )
        try:
            initiating_actor = _initiating_actor(factory, claimed)
            resolved_model = model
            if resolved_model is None:
                resolved_model, _provider = build_real_text_gateway(
                    resolved_settings,
                    audit_sink=SqlAlchemyAttemptAuditSink(factory),
                )
            result = await NodeExecutionService(
                SqlAlchemyNodeExecutionTransactionFactory(
                    factory,
                    initiating_actor,
                    generation_job_id=job_id,
                ),
                resolved_model,
            ).execute(
                node_run_id,
                request_id=f"generation-job:{job_id}",
                user_revision=_user_revision(claimed.creation_request_json),
            )
        except NodeExecutionError as exc:
            status = _complete_job(
                factory,
                worker_actor,
                job_id,
                worker_id=worker_id,
                idempotency_ttl_seconds=resolved_settings.idempotency_ttl_seconds,
                error_code=exc.code,
            )
            return "cancelled" if status == "cancelled" else "failed"
        except Exception:
            logger.exception("node_execution_job_failed", extra={"job_id": str(job_id)})
            _terminalize_node_failure(
                factory,
                worker_actor,
                node_run_id,
                code="NODE_EXECUTION_WORKER_FAILED",
            )
            _complete_job(
                factory,
                worker_actor,
                job_id,
                worker_id=worker_id,
                idempotency_ttl_seconds=resolved_settings.idempotency_ttl_seconds,
                error_code="NODE_EXECUTION_WORKER_FAILED",
            )
            raise
        status = _complete_job(
            factory,
            worker_actor,
            job_id,
            worker_id=worker_id,
            idempotency_ttl_seconds=resolved_settings.idempotency_ttl_seconds,
            result_artifact_version_id=result.artifact_version_id,
        )
        return "succeeded" if status == "succeeded" else "ignored"
    finally:
        engine.dispose()


def _job_facts(
    factory: sessionmaker[Session],
    job_id: UUID,
) -> tuple[UUID, UUID] | None:
    with factory() as session:
        job = session.get(GenerationJob, job_id)
        if job is None or job.job_type != "workflow.node" or job.node_run_id is None:
            return None
        return job.organization_id, job.node_run_id


def _initiating_actor(
    factory: sessionmaker[Session],
    job: GenerationJob,
) -> ActorContext:
    with factory() as session:
        return _resolve_initiating_actor(session, job)


def _resolve_initiating_actor(session: Session, job: GenerationJob) -> ActorContext:
    principal = session.get(Principal, job.created_by)
    if (
        principal is None
        or principal.organization_id != job.organization_id
        or principal.user_id is None
    ):
        raise RuntimeError("node execution job has no active initiating principal")
    actor = IdentityRepository(session).resolve_actor(
        AuthenticatedIdentity(
            user_id=principal.user_id,
            organization_id=job.organization_id,
        )
    )
    if actor.principal_id != job.created_by:
        raise RuntimeError("node execution job principal binding is ambiguous")
    return actor


def _user_revision(payload: dict[str, object] | None) -> str | None:
    if not payload or "user_revision" not in payload:
        return None
    value = payload["user_revision"]
    if not isinstance(value, str) or len(value) > 6_000:
        raise RuntimeError("node execution job contains an invalid user revision")
    return value


def _complete_job(
    factory: sessionmaker[Session],
    actor: ActorContext,
    job_id: UUID,
    *,
    worker_id: str,
    idempotency_ttl_seconds: int,
    error_code: str | None = None,
    result_artifact_version_id: UUID | None = None,
) -> str | None:
    with factory() as session, session.begin():
        completed = GenerationJobService(
            session,
            actor=actor,
            idempotency_ttl_seconds=idempotency_ttl_seconds,
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
        job = session.get(GenerationJob, job_id)
        if job is None or job.status != "cancelled":
            return False
        workflow = SqlAlchemyWorkflowExecutionPort(
            session,
            _resolve_initiating_actor(session, job),
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
) -> None:
    try:
        with factory() as session, session.begin():
            SqlAlchemyWorkflowExecutionPort(session, actor).terminalize(
                node_run_id,
                code=code,
                cancelled=False,
            )
    except (ApiError, WorkflowExecutionPortError):
        logger.exception(
            "node_execution_terminalization_failed",
            extra={"node_run_id": str(node_run_id)},
        )
