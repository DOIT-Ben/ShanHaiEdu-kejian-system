from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.assets.video_port import GeneratedVideoFile, VideoAssetPort
from apps.api.creation.video_port import VideoCreationPort, VideoCreationRouting
from apps.api.database import utc_now
from apps.api.identity.context import ActorContext, system_actor
from apps.api.jobs.service import GenerationJobService
from apps.api.jobs.video_port import VideoJobLease, VideoJobPort
from apps.api.jobs.worker_port import VideoGenerationJobRouting
from apps.api.model_gateway.contracts import GeneratedFileFact
from apps.api.model_gateway.video_smoke import VideoProbeResult
from apps.api.settings import Settings
from apps.api.uploads.storage import ObjectMetadata
from apps.api.workflows.service import WorkflowRuntimeService
from apps.api.workflows.video_scope_port import VideoWorkflowPort
from workflow.node_state import NodeStatus


@dataclass(frozen=True, slots=True)
class ValidatedVideo:
    file: GeneratedFileFact
    metadata: ObjectMetadata
    probe: VideoProbeResult
    provider: str
    model: str


def persist_success(
    factory: sessionmaker[Session],
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    *,
    worker_id: str,
    validated: ValidatedVideo,
    settings: Settings,
) -> str:
    actor = system_actor(routing.organization_id)
    with factory() as session, session.begin():
        jobs = VideoJobPort(session, actor)
        lease = jobs.lock_lease(job_id)
        if lease is None or not lease.owned_running(worker_id):
            return _terminal_outcome(lease)
        creation = VideoCreationPort(session, actor)
        if creation.result_for_job(job_id) is not None:
            return "ignored"
        now = utc_now()
        duration_ms = round(validated.probe.duration_seconds * 1000)
        version = VideoAssetPort(session, actor).persist_generated(
            job_id, _generated_file(routing, job_id, validated, settings, duration_ms), now=now
        )
        creation.persist_result(
            _creation_routing(routing),
            job_id,
            version.id,
            {
                "mime_type": version.mime_type,
                "byte_size": version.byte_size,
                "sha256": version.sha256,
                "duration_ms": duration_ms,
                "width": validated.probe.width,
                "height": validated.probe.height,
            },
            now=now,
        )
        WorkflowRuntimeService(session, actor).transition_node(
            routing.node_run_id, NodeStatus.REVIEW_REQUIRED
        )
        completed = _jobs(session, actor, settings).complete(job_id, worker_id=worker_id)
        return (
            "succeeded" if completed is not None and completed.status == "succeeded" else "ignored"
        )


def persist_failure(
    factory: sessionmaker[Session],
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    *,
    worker_id: str,
    error_code: str,
    settings: Settings,
) -> str:
    actor = system_actor(routing.organization_id)
    with factory() as session, session.begin():
        lease = VideoJobPort(session, actor).lock_lease(job_id)
        if lease is None or lease.status in {"succeeded", "failed", "cancelled"}:
            return _terminal_outcome(lease)
        if lease.cancel_requested:
            return _cancel_locked(session, routing, job_id, worker_id=worker_id, settings=settings)
        if not lease.owned_running(worker_id):
            return "ignored"
        VideoCreationPort(session, actor).mark_failure(_creation_routing(routing))
        workflows = VideoWorkflowPort(session, actor)
        if workflows.set_last_error_if_active(routing.node_run_id, error_code):
            WorkflowRuntimeService(session, actor).transition_node(
                routing.node_run_id, NodeStatus.FAILED
            )
        completed = _jobs(session, actor, settings).complete(
            job_id, worker_id=worker_id, error_code=error_code
        )
        return "failed" if completed is not None and completed.status == "failed" else "ignored"


def persist_cancelled(
    factory: sessionmaker[Session],
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    *,
    worker_id: str,
    settings: Settings,
) -> str:
    actor = system_actor(routing.organization_id)
    with factory() as session, session.begin():
        lease = VideoJobPort(session, actor).lock_lease(job_id)
        if lease is None or lease.status in {"succeeded", "failed"}:
            return _terminal_outcome(lease)
        return _cancel_locked(session, routing, job_id, worker_id=worker_id, settings=settings)


def update_progress(
    factory: sessionmaker[Session],
    organization_id: UUID,
    job_id: UUID,
    *,
    worker_id: str,
    progress_percent: int,
    settings: Settings,
) -> None:
    with factory() as session, session.begin():
        _jobs(session, system_actor(organization_id), settings).update_progress(
            job_id,
            worker_id=worker_id,
            progress_percent=progress_percent,
            message="Waiting for video provider",
        )


def _cancel_locked(
    session: Session,
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    *,
    worker_id: str,
    settings: Settings,
) -> str:
    actor = system_actor(routing.organization_id)
    VideoCreationPort(session, actor).mark_cancelled(_creation_routing(routing))
    if VideoWorkflowPort(session, actor).is_active(routing.node_run_id):
        runtime = WorkflowRuntimeService(session, actor)
        runtime.transition_node(routing.node_run_id, NodeStatus.CANCEL_REQUESTED)
        runtime.transition_node(routing.node_run_id, NodeStatus.CANCELLED)
    completed = _jobs(session, actor, settings).complete(job_id, worker_id=worker_id)
    return "cancelled" if completed is not None and completed.status == "cancelled" else "ignored"


def _generated_file(
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    validated: ValidatedVideo,
    settings: Settings,
    duration_ms: int,
) -> GeneratedVideoFile:
    return GeneratedVideoFile(
        storage_bucket=settings.object_storage_bucket,
        storage_key=validated.file.storage_key,
        byte_size=validated.metadata.size_bytes,
        sha256=validated.file.sha256,
        etag=validated.metadata.etag,
        width=validated.probe.width,
        height=validated.probe.height,
        duration_ms=duration_ms,
        derived_from_version_id=_uuid_fact(routing.creation_request, "keyframe_file_version_id"),
        metadata={
            "runtime": "video.golden_slice",
            "generation_job_id": str(job_id),
            "provider": validated.provider,
            "model": validated.model,
        },
    )


def _creation_routing(routing: VideoGenerationJobRouting) -> VideoCreationRouting:
    return VideoCreationRouting(
        batch_id=routing.creation_batch_id,
        prompt_version_id=routing.creation_prompt_version_id,
    )


def _jobs(session: Session, actor: ActorContext, settings: Settings) -> GenerationJobService:
    return GenerationJobService(
        session,
        actor=actor,
        idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
    )


def _terminal_outcome(lease: VideoJobLease | None) -> str:
    if lease is not None and lease.status in {"failed", "cancelled"}:
        return lease.status
    return "ignored"


def _uuid_fact(payload: dict[str, object], key: str) -> UUID:
    try:
        return UUID(str(payload[key]))
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("VIDEO_INPUTS_INVALID") from exc
