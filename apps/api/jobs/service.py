"""Transactional generation-job commands used by HTTP and workers."""

from __future__ import annotations

from collections.abc import Collection
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.repository import GenerationJobRepository
from apps.api.jobs.schemas import GenerationJobRead
from apps.api.jobs.state_machine import InvalidJobTransition, require_transition
from apps.api.reliability.events import EventResource, EventWriter, append_outbox_only
from apps.api.reliability.idempotency import CommandResult, IdempotencyService


class GenerationJobCancellationReader:
    """Expose cancellation state without leaking the jobs ORM model."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def requested_ids(self, job_ids: Collection[UUID]) -> set[UUID]:
        if not job_ids:
            return set()
        return set(
            self._session.scalars(
                select(GenerationJob.id).where(
                    GenerationJob.id.in_(job_ids),
                    (
                        GenerationJob.status.in_(("cancel_requested", "cancelled"))
                        | GenerationJob.cancel_requested_at.is_not(None)
                    ),
                )
            )
        )


class GenerationJobService:
    def __init__(
        self,
        session: Session,
        *,
        actor: ActorContext,
        idempotency_ttl_seconds: int,
    ) -> None:
        self._session = session
        self._actor = actor
        self._repository = GenerationJobRepository(session, actor.organization_id)
        self._events = EventWriter(session, actor.organization_id)
        self._idempotency = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=idempotency_ttl_seconds,
        )

    def request_cancel(
        self,
        job_id: UUID,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> GenerationJobRead:
        self._authorize_cancel(job_id, for_update=False)
        payload = {"job_id": str(job_id), "command": "cancel"}

        def command() -> CommandResult:
            job = self._require_job(job_id, for_update=True)
            if job.status == "cancel_requested":
                return self._result(job, 202)
            if job.status in {"succeeded", "failed", "cancelled"}:
                raise ApiError(
                    status_code=409,
                    code="PRECONDITION_NOT_MET",
                    message="The generation job can no longer be cancelled.",
                )
            self._transition(job, "cancel_requested")
            job.cancel_requested_at = utc_now()
            job.progress_message = "Cancellation requested"
            job.updated_by = self._actor.principal_id
            job.lock_version += 1
            self._append_job_event(job, request_id=request_id)
            return self._result(job, 202)

        result = self._idempotency.execute(
            scope=f"generation_jobs.cancel:{self._actor.principal_id}",
            key=idempotency_key,
            payload=payload,
            authorize=lambda: self._authorize_cancel(job_id, for_update=True),
            command=command,
        )
        return GenerationJobRead.model_validate(result.body)

    def claim(self, job_id: UUID, *, worker_id: str, lease_seconds: int) -> GenerationJob | None:
        self._require_system_actor()
        job = self._repository.get(job_id, for_update=True)
        if job is None or job.status in {"succeeded", "failed", "cancelled"}:
            return None
        now = utc_now()
        if job.status == "cancel_requested":
            self._transition(job, "cancelled")
            job.finished_at = now
            job.progress_message = "Cancelled before execution"
            job.lease_owner = None
            job.lease_expires_at = None
            self._append_job_event(job, request_id=f"worker:{worker_id}")
            return None
        if job.status == "running" and job.lease_expires_at is not None:
            if job.lease_expires_at >= now and job.lease_owner != worker_id:
                return None
        if job.status == "queued":
            self._transition(job, "running")
            job.started_at = job.started_at or now
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.attempt_count += 1
        job.progress_message = "Processing deterministic stage-zero task"
        job.updated_by = self._actor.principal_id
        job.lock_version += 1
        self._append_job_event(job, request_id=f"worker:{worker_id}")
        return job

    def update_progress(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        progress_percent: int,
        message: str,
    ) -> GenerationJob | None:
        self._require_system_actor()
        job = self._repository.get(job_id, for_update=True)
        if job is None or job.status != "running" or job.lease_owner != worker_id:
            return None
        if job.cancel_requested_at is not None:
            self._transition(job, "cancel_requested")
            job.progress_message = "Cancellation requested"
        else:
            job.progress_percent = progress_percent
            job.progress_message = message
        job.updated_by = self._actor.principal_id
        job.lock_version += 1
        self._append_job_event(job, request_id=f"worker:{worker_id}")
        return job

    def complete(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        error_code: str | None = None,
    ) -> GenerationJob | None:
        self._require_system_actor()
        job = self._repository.get(job_id, for_update=True)
        if job is None or job.status in {"succeeded", "failed", "cancelled"}:
            return job
        if job.status == "cancel_requested" or job.cancel_requested_at is not None:
            target = "cancelled"
        else:
            if job.status != "running" or job.lease_owner != worker_id:
                return None
            target = "failed" if error_code else "succeeded"
        self._transition(job, target)
        job.progress_percent = 100 if target == "succeeded" else job.progress_percent
        job.progress_message = {
            "succeeded": "Deterministic stage-zero task completed",
            "failed": "Deterministic stage-zero task failed",
            "cancelled": "Generation job cancelled",
        }[target]
        job.error_code = error_code
        job.finished_at = utc_now()
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_by = self._actor.principal_id
        job.lock_version += 1
        self._append_job_event(job, request_id=f"worker:{worker_id}")
        return job

    def _require_job(self, job_id: UUID, *, for_update: bool) -> GenerationJob:
        job = self._repository.get(job_id, for_update=for_update)
        if job is None:
            raise self._job_not_found()
        return job

    def _authorize_cancel(self, job_id: UUID, *, for_update: bool) -> GenerationJob:
        job = self._require_job(job_id, for_update=for_update)
        if job.project_id is None:
            raise self._job_not_found()
        ProjectAccessService(self._session, self._actor).require(
            job.project_id,
            ProjectAction.GENERATE,
            for_update=for_update,
        )
        return job

    def _require_system_actor(self) -> None:
        if not self._actor.is_system:
            raise ValueError("worker job transitions require a system actor")

    @staticmethod
    def _job_not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="GENERATION_JOB_NOT_FOUND",
            message="The generation job was not found.",
        )

    @staticmethod
    def _transition(job: GenerationJob, target: str) -> None:
        try:
            require_transition(job.status, target)
        except InvalidJobTransition as exc:
            raise ApiError(
                status_code=409,
                code="PRECONDITION_NOT_MET",
                message="The generation job state does not allow this command.",
            ) from exc
        job.status = target

    def _append_job_event(self, job: GenerationJob, *, request_id: str) -> None:
        payload = {
            "status": job.status,
            "progress_percent": job.progress_percent,
            "attempt_count": job.attempt_count,
        }
        resource = EventResource(type="generation_job", id=job.id)
        if job.project_id is not None:
            self._events.append(
                project_id=job.project_id,
                event_type="generation.job.progress",
                resource=resource,
                payload=payload,
                request_id=request_id,
            )
        else:
            append_outbox_only(
                self._session,
                self._actor.organization_id,
                event_type="generation.job.progress",
                resource=resource,
                payload=payload,
                request_id=request_id,
            )

    @staticmethod
    def _result(job: GenerationJob, status_code: int) -> CommandResult:
        body: dict[str, Any] = GenerationJobRead.model_validate(job).model_dump(mode="json")
        return CommandResult(
            status_code=status_code,
            body=body,
            resource_type="generation_job",
            resource_id=job.id,
        )
