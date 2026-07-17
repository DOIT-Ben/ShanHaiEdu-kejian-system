"""Transactional generation-job commands used by HTTP and workers."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.models import SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.repository import GenerationJobRepository
from apps.api.jobs.schemas import GenerationJobRead
from apps.api.jobs.state_machine import InvalidJobTransition, require_transition
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.idempotency import CommandResult, IdempotencyService


class GenerationJobService:
    def __init__(self, session: Session, *, idempotency_ttl_seconds: int) -> None:
        self._session = session
        self._repository = GenerationJobRepository(session, SYSTEM_ORGANIZATION_ID)
        self._events = EventWriter(session, SYSTEM_ORGANIZATION_ID)
        self._idempotency = IdempotencyService(
            session,
            SYSTEM_ORGANIZATION_ID,
            ttl_seconds=idempotency_ttl_seconds,
        )

    def request_cancel(
        self,
        job_id: UUID,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> GenerationJobRead:
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
            self._append_job_event(job, request_id=request_id)
            return self._result(job, 202)

        result = self._idempotency.execute(
            scope="generation_jobs.cancel",
            key=idempotency_key,
            payload=payload,
            command=command,
        )
        return GenerationJobRead.model_validate(result.body)

    def claim(self, job_id: UUID, *, worker_id: str, lease_seconds: int) -> GenerationJob | None:
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
        job.updated_by = SYSTEM_PRINCIPAL_ID
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
        job = self._repository.get(job_id, for_update=True)
        if job is None or job.status != "running" or job.lease_owner != worker_id:
            return None
        if job.cancel_requested_at is not None:
            self._transition(job, "cancel_requested")
            job.progress_message = "Cancellation requested"
        else:
            job.progress_percent = progress_percent
            job.progress_message = message
        job.updated_by = SYSTEM_PRINCIPAL_ID
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
        job.updated_by = SYSTEM_PRINCIPAL_ID
        job.lock_version += 1
        self._append_job_event(job, request_id=f"worker:{worker_id}")
        return job

    def _require_job(self, job_id: UUID, *, for_update: bool) -> GenerationJob:
        job = self._repository.get(job_id, for_update=for_update)
        if job is None:
            raise ApiError(
                status_code=404,
                code="GENERATION_JOB_NOT_FOUND",
                message="The generation job was not found.",
            )
        return job

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
        if job.project_id is None:
            raise ValueError("stage-zero generation jobs require a project")
        self._events.append(
            project_id=job.project_id,
            event_type="generation.job.progress",
            resource=EventResource(type="generation_job", id=job.id),
            payload={
                "status": job.status,
                "progress_percent": job.progress_percent,
                "attempt_count": job.attempt_count,
            },
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
