"""Dramatiq actors for deterministic stage-zero processing."""

from __future__ import annotations

import logging
import socket
from uuid import UUID, uuid4

import dramatiq
from sqlalchemy import select

from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import ActorContext, system_actor
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.service import GenerationJobService
from apps.api.settings import get_settings
from workers.material_parse import run_material_parse_job

logger = logging.getLogger(__name__)


def run_deterministic_job(job_id: UUID, *, worker_id: str | None = None) -> str:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("worker database persistence is not configured")
    resolved_worker_id = worker_id or f"{socket.gethostname()}:{uuid4()}"
    engine = build_engine(settings.database_url.get_secret_value())
    factory = build_session_factory(engine)
    actor: ActorContext | None = None
    try:
        with factory() as session:
            organization_id = session.scalar(
                select(GenerationJob.organization_id).where(GenerationJob.id == job_id)
            )
        if organization_id is None:
            return "ignored"
        actor = system_actor(organization_id)
        with factory() as session, session.begin():
            claimed = GenerationJobService(
                session,
                actor=actor,
                idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
            ).claim(
                job_id,
                worker_id=resolved_worker_id,
                lease_seconds=settings.worker_lease_seconds,
            )
        if claimed is None:
            return "ignored"
        with factory() as session, session.begin():
            GenerationJobService(
                session,
                actor=actor,
                idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
            ).update_progress(
                job_id,
                worker_id=resolved_worker_id,
                progress_percent=50,
                message="Deterministic inspection in progress",
            )
        with factory() as session, session.begin():
            GenerationJobService(
                session,
                actor=actor,
                idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
            ).complete(job_id, worker_id=resolved_worker_id)
        return "succeeded"
    except Exception:
        logger.exception("deterministic_job_failed", extra={"job_id": str(job_id)})
        if actor is None:
            raise
        try:
            with factory() as session, session.begin():
                GenerationJobService(
                    session,
                    actor=actor,
                    idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
                ).complete(
                    job_id,
                    worker_id=resolved_worker_id,
                    error_code="DETERMINISTIC_TASK_FAILED",
                )
        except Exception:
            logger.exception("deterministic_job_failure_persist_failed")
        raise
    finally:
        engine.dispose()


def run_generation_job(job_id: UUID, *, worker_id: str | None = None) -> str:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("worker database persistence is not configured")
    resolved_worker_id = worker_id or f"{socket.gethostname()}:{uuid4()}"
    engine = build_engine(settings.database_url.get_secret_value())
    try:
        with build_session_factory(engine)() as session:
            job_type = session.scalar(
                select(GenerationJob.job_type).where(GenerationJob.id == job_id)
            )
    finally:
        engine.dispose()
    if job_type == "material.parse":
        return run_material_parse_job(job_id, worker_id=resolved_worker_id)
    return run_deterministic_job(job_id, worker_id=resolved_worker_id)


@dramatiq.actor(max_retries=5, min_backoff=1_000, max_backoff=30_000)
def process_generation_job(job_id: str) -> None:
    run_generation_job(UUID(job_id))
