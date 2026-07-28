from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import ActorContext, system_actor
from apps.api.identity.repository import IdentityRepository
from apps.api.jobs.service import GenerationJobService
from apps.api.jobs.worker_port import (
    GenerationJobRoutingReader,
    VideoGenerationJobRouting,
)
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.contracts import ModelGatewayError, VideoOperationStatus
from apps.api.model_gateway.factory import (
    build_provider_media_reference_resolver,
    build_real_video_gateway,
)
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.model_gateway.object_storage_video_store import ObjectStorageVideoResultStore
from apps.api.settings import Settings, get_settings
from apps.api.uploads.storage import ObjectStorage, build_object_storage
from apps.api.workflows.service import WorkflowRuntimeService
from workers.video_generation_persistence import (
    persist_cancelled,
    persist_failure,
    persist_success,
)
from workers.video_generation_runtime import (
    VideoGenerationCancelled,
    VideoGenerationFailure,
    build_video_request,
    poll_until_terminal,
    validate_video_result,
)
from workflow.node_state import NodeStatus

logger = logging.getLogger(__name__)


async def execute_video_generation_job(
    job_id: UUID,
    *,
    worker_id: str,
    gateway: ModelGateway | None = None,
    storage: ObjectStorage | None = None,
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    if resolved_settings.database_url is None:
        raise RuntimeError("worker database persistence is not configured")
    engine = build_engine(resolved_settings.database_url.get_secret_value())
    factory = build_session_factory(engine)
    resolved_storage = storage or build_object_storage(resolved_settings)
    if resolved_storage is None:
        engine.dispose()
        raise RuntimeError("video worker object storage is not configured")
    provider = None
    media_session: Session | None = None
    try:
        resolved_gateway = gateway
        if resolved_gateway is None:
            media_session = factory()
            resolver = build_provider_media_reference_resolver(
                resolved_settings,
                session=media_session,
                storage=resolved_storage,
            )
            resolved_gateway, provider = build_real_video_gateway(
                resolved_settings,
                store=ObjectStorageVideoResultStore(
                    resolved_storage,
                    bucket=resolved_settings.object_storage_bucket,
                    max_bytes=resolved_settings.video_provider_max_download_bytes,
                ),
                media_reference_resolver=resolver,
                audit_sink=SqlAlchemyAttemptAuditSink(factory),
            )
        return await _execute(
            factory,
            job_id,
            worker_id=worker_id,
            gateway=resolved_gateway,
            storage=resolved_storage,
            settings=resolved_settings,
        )
    finally:
        if provider is not None:
            await provider.aclose()
        if media_session is not None:
            media_session.close()
        engine.dispose()


async def _execute(
    factory: sessionmaker[Session],
    job_id: UUID,
    *,
    worker_id: str,
    gateway: ModelGateway,
    storage: ObjectStorage,
    settings: Settings,
) -> str:
    routing = _routing(factory, job_id)
    if routing is None or routing.status in {"succeeded", "failed", "cancelled"}:
        return "ignored"
    if not _claim(factory, routing, job_id, worker_id=worker_id, settings=settings):
        if not _cancel_requested(factory, job_id):
            return "ignored"
        return persist_cancelled(
            factory,
            routing,
            job_id,
            worker_id=worker_id,
            settings=settings,
        )
    try:
        return await _run_generation(
            factory,
            routing,
            job_id,
            worker_id=worker_id,
            gateway=gateway,
            storage=storage,
            settings=settings,
        )
    except VideoGenerationCancelled:
        return _cancel(factory, routing, job_id, worker_id, settings)
    except VideoGenerationFailure as exc:
        return _fail(factory, routing, job_id, worker_id, exc.code, settings)
    except ModelGatewayError as exc:
        return _fail(factory, routing, job_id, worker_id, exc.code.value, settings)
    except Exception:
        logger.exception("video_generation_job_failed", extra={"job_id": str(job_id)})
        persist_failure(
            factory,
            routing,
            job_id,
            worker_id=worker_id,
            error_code="VIDEO_WORKER_FAILED",
            settings=settings,
        )
        raise


def _cancel(
    factory: sessionmaker[Session],
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    worker_id: str,
    settings: Settings,
) -> str:
    return persist_cancelled(factory, routing, job_id, worker_id=worker_id, settings=settings)


def _fail(
    factory: sessionmaker[Session],
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    worker_id: str,
    error_code: str,
    settings: Settings,
) -> str:
    return persist_failure(
        factory,
        routing,
        job_id,
        worker_id=worker_id,
        error_code=error_code,
        settings=settings,
    )


async def _run_generation(
    factory: sessionmaker[Session],
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    *,
    worker_id: str,
    gateway: ModelGateway,
    storage: ObjectStorage,
    settings: Settings,
) -> str:
    initiating_actor = _initiating_actor(factory, routing)
    request, audit_context = build_video_request(factory, routing, job_id, initiating_actor)
    result = await gateway.submit_video(
        request,
        audit_context=audit_context,
        media_organization_id=routing.organization_id,
    )
    result = await poll_until_terminal(
        factory,
        routing,
        job_id,
        worker_id=worker_id,
        gateway=gateway,
        audit_context=audit_context,
        initial=result,
        settings=settings,
    )
    if result.status is not VideoOperationStatus.SUCCEEDED:
        raise VideoGenerationFailure("VIDEO_PROVIDER_FAILED")
    validated = await validate_video_result(result, storage=storage, settings=settings)
    return persist_success(
        factory,
        routing,
        job_id,
        worker_id=worker_id,
        validated=validated,
        settings=settings,
    )


def _routing(
    factory: sessionmaker[Session],
    job_id: UUID,
) -> VideoGenerationJobRouting | None:
    with factory() as session:
        return GenerationJobRoutingReader(session).get_video_golden_slice(job_id)


def _cancel_requested(factory: sessionmaker[Session], job_id: UUID) -> bool:
    with factory() as session:
        return GenerationJobRoutingReader(session).video_cancel_requested(job_id)


def _claim(
    factory: sessionmaker[Session],
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    *,
    worker_id: str,
    settings: Settings,
) -> bool:
    actor = system_actor(routing.organization_id)
    with factory() as session, session.begin():
        claimed = GenerationJobService(
            session,
            actor=actor,
            idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
        ).claim(
            job_id,
            worker_id=worker_id,
            lease_seconds=max(
                settings.worker_lease_seconds,
                settings.video_provider_max_wait_seconds + 30,
            ),
        )
        if claimed is None:
            return False
        WorkflowRuntimeService(session, actor).transition_node(
            routing.node_run_id,
            NodeStatus.RUNNING,
        )
        return True


def _initiating_actor(
    factory: sessionmaker[Session],
    routing: VideoGenerationJobRouting,
) -> ActorContext:
    with factory() as session:
        return IdentityRepository(session).resolve_actor_for_principal(
            routing.created_by,
            routing.organization_id,
        )
