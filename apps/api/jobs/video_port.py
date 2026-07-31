"""Generation-job-owned commands and projections for the video golden slice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.schemas import AcceptedJobData, GenerationJobRead
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.idempotency import canonical_request_hash


@dataclass(frozen=True, slots=True)
class VideoJobInput:
    project_id: UUID
    lesson_id: UUID
    node_run_id: UUID
    prompt_version_id: UUID
    batch_id: UUID
    request_payload: dict[str, object]
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class VideoJobProjection:
    read: GenerationJobRead
    creation_request: dict[str, object]


@dataclass(frozen=True, slots=True)
class VideoJobLease:
    status: str
    lease_owner: str | None
    cancel_requested: bool

    def owned_running(self, worker_id: str) -> bool:
        return self.status == "running" and self.lease_owner == worker_id


@dataclass(frozen=True, slots=True)
class VideoCleanupJobFact:
    organization_id: UUID
    project_id: UUID | None
    lesson_unit_id: UUID | None
    job_type: str
    status: str
    lease_expires_at: datetime | None


class VideoJobCleanupPort:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fact(self, job_id: UUID, *, for_update: bool = False) -> VideoCleanupJobFact | None:
        statement = select(GenerationJob).where(
            GenerationJob.id == job_id,
            GenerationJob.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update(of=GenerationJob)
        job = self._session.scalar(statement)
        if job is None:
            return None
        return VideoCleanupJobFact(
            organization_id=job.organization_id,
            project_id=job.project_id,
            lesson_unit_id=job.lesson_unit_id,
            job_type=job.job_type,
            status=job.status,
            lease_expires_at=job.lease_expires_at,
        )


class VideoJobPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def active_exists(self, project_id: UUID, lesson_id: UUID, *, for_update: bool = False) -> bool:
        statement = select(GenerationJob.id).where(
            GenerationJob.organization_id == self._actor.organization_id,
            GenerationJob.project_id == project_id,
            GenerationJob.lesson_unit_id == lesson_id,
            GenerationJob.workflow_node_key == "video.shots.generate",
            GenerationJob.status.in_(("created", "queued", "running", "cancel_requested")),
            GenerationJob.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update(of=GenerationJob)
        return self._session.scalar(statement) is not None

    def latest(self, project_id: UUID, lesson_id: UUID) -> VideoJobProjection | None:
        job = self._session.scalar(
            select(GenerationJob)
            .where(
                GenerationJob.organization_id == self._actor.organization_id,
                GenerationJob.project_id == project_id,
                GenerationJob.lesson_unit_id == lesson_id,
                GenerationJob.workflow_node_key == "video.shots.generate",
                GenerationJob.deleted_at.is_(None),
            )
            .order_by(GenerationJob.id.desc())
            .limit(1)
        )
        if job is None:
            return None
        return VideoJobProjection(
            read=GenerationJobRead.model_validate(job),
            creation_request=dict(job.creation_request_json or {}),
        )

    def create(self, data: VideoJobInput, *, request_id: str) -> AcceptedJobData:
        job = GenerationJob(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=data.project_id,
            node_run_id=data.node_run_id,
            lesson_unit_id=data.lesson_id,
            workflow_node_key="video.shots.generate",
            creation_prompt_version_id=data.prompt_version_id,
            creation_batch_id=data.batch_id,
            creation_request_json=data.request_payload,
            job_type="video.golden_slice",
            status="queued",
            progress_percent=0,
            progress_message="Video generation queued",
            idempotency_key=data.idempotency_key,
            request_hash=canonical_request_hash(data.request_payload),
            priority=100,
            attempt_count=0,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(job)
        self._session.flush()
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=data.project_id,
            event_type="generation.job.queued",
            resource=EventResource(type="generation_job", id=job.id),
            payload={
                "status": "queued",
                "progress_percent": 0,
                "attempt_count": 0,
                "node_run_id": str(data.node_run_id),
                "lesson_unit_id": str(data.lesson_id),
                "workflow_node_key": "video.shots.generate",
            },
            request_id=request_id,
        )
        return AcceptedJobData(
            job_id=job.id,
            status="queued",
            events_url=f"/api/v2/generation-jobs/{job.id}/events/stream",
        )

    def lock_lease(self, job_id: UUID) -> VideoJobLease | None:
        job = self._session.get(GenerationJob, job_id, with_for_update=True)
        if job is None or job.organization_id != self._actor.organization_id:
            return None
        return VideoJobLease(
            status=job.status,
            lease_owner=job.lease_owner,
            cancel_requested=job.status == "cancel_requested"
            or job.cancel_requested_at is not None,
        )
