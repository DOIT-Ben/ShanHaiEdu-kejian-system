from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.assets.video_port import VideoAssetPort
from apps.api.creation.video_port import VideoCreationPort
from apps.api.identity.context import ActorContext
from apps.api.jobs.worker_port import GenerationJobRoutingReader, VideoGenerationJobRouting
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    GeneratedFileFact,
    MediaReference,
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    VideoGatewayResult,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
    VideoResultScope,
)
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.model_gateway.object_storage_video_store import (
    ObjectStorageVideoResultStore,
    build_video_staging_key,
)
from apps.api.model_gateway.video_smoke import VideoProbeError, VideoProbeResult, probe_mp4
from apps.api.model_gateway.video_store import StoredVideoFile
from apps.api.settings import Settings
from apps.api.uploads.storage import ObjectMetadata, ObjectStorage, ObjectStorageError
from workers.video_generation_persistence import ValidatedVideo, update_progress


class VideoGenerationFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class VideoGenerationCancelled(RuntimeError):
    pass


def build_video_request(
    factory: sessionmaker[Session],
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    actor: ActorContext,
) -> tuple[VideoModelRequest, ModelAuditContext]:
    keyframe_id = _uuid_fact(routing.creation_request, "keyframe_file_version_id")
    with factory() as session:
        prompt = VideoCreationPort(session, actor).prompt_text(routing.creation_prompt_version_id)
        keyframe = VideoAssetPort(session, actor).file_version(keyframe_id)
    if (
        prompt is None
        or keyframe is None
        or keyframe.scan_status != "clean"
        or not keyframe.mime_type.startswith("image/")
    ):
        raise VideoGenerationFailure("VIDEO_INPUTS_INVALID")
    request = VideoModelRequest(
        capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
        request_id=f"video-job:{job_id}:submit",
        prompt=prompt,
        duration_seconds=6,
        references=[
            MediaReference(
                file_version_id=keyframe.id,
                mime_type=keyframe.mime_type,
            )
        ],
        result_scope=_video_result_scope(routing, job_id),
    )
    audit = ModelAuditContext(
        organization_id=routing.organization_id,
        user_id=actor.user_id,
        project_id=routing.project_id,
        node_run_id=routing.node_run_id,
        generation_job_id=job_id,
        lesson_unit_id=routing.lesson_unit_id,
    )
    return request, audit


async def poll_until_terminal(
    factory: sessionmaker[Session],
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    *,
    worker_id: str,
    gateway: ModelGateway,
    audit_context: ModelAuditContext,
    initial: VideoGatewayResult,
    settings: Settings,
) -> VideoGatewayResult:
    result = initial
    started = time.monotonic()
    poll_no = 0
    while result.status in {VideoOperationStatus.SUBMITTED, VideoOperationStatus.POLLING}:
        if time.monotonic() - started >= settings.video_provider_max_wait_seconds:
            raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True)
        if _cancel_requested(factory, job_id):
            await _cancel_provider(
                gateway,
                result,
                routing,
                job_id,
                audit_context,
            )
            raise VideoGenerationCancelled
        await asyncio.sleep(settings.video_provider_poll_seconds)
        poll_no += 1
        update_progress(
            factory,
            routing.organization_id,
            job_id,
            worker_id=worker_id,
            progress_percent=min(85, 15 + poll_no * 10),
            settings=settings,
        )
        if result.provider_task_id is None:
            raise VideoGenerationFailure("VIDEO_PROVIDER_STATE_INVALID")
        result = await gateway.poll_video(
            VideoPollRequest(
                capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
                request_id=f"video-job:{job_id}:poll:{poll_no}",
                provider_task_id=result.provider_task_id,
                result_scope=_video_result_scope(routing, job_id),
            ),
            audit_context=audit_context,
        )
    return result


async def validate_video_result(
    result: VideoGatewayResult,
    *,
    result_scope: VideoResultScope,
    storage: ObjectStorage,
    settings: Settings,
) -> ValidatedVideo:
    file = _require_staged_file(result, result_scope)
    _, probe = await _download_and_probe(file, storage=storage, settings=settings)
    promoted_file, final_metadata = _promote_validated_file(
        file,
        result_scope=result_scope,
        storage=storage,
        settings=settings,
    )
    return ValidatedVideo(
        file=promoted_file,
        metadata=final_metadata,
        probe=probe,
        provider=result.route.provider,
        model=result.actual_model,
        staging_key=file.storage_key,
    )


def _require_staged_file(
    result: VideoGatewayResult,
    result_scope: VideoResultScope,
) -> GeneratedFileFact:
    if len(result.files) != 1:
        raise VideoGenerationFailure("VIDEO_FILE_INVALID")
    file = result.files[0]
    if file.mime_type != "video/mp4" or (
        file.duration_seconds is not None and file.duration_seconds != 6
    ):
        raise VideoGenerationFailure("VIDEO_FILE_INVALID")
    if result.provider_task_id is None or file.storage_key != build_video_staging_key(
        result_scope,
        provider_name=result.route.provider,
        provider_task_id=result.provider_task_id,
    ):
        raise VideoGenerationFailure("VIDEO_FILE_INVALID")
    return file


async def _download_and_probe(
    file: GeneratedFileFact,
    *,
    storage: ObjectStorage,
    settings: Settings,
) -> tuple[ObjectMetadata, VideoProbeResult]:
    with tempfile.TemporaryDirectory(prefix="shanhaiedu-video-worker-") as directory:
        path = Path(directory) / "candidate.mp4"
        try:
            metadata = await asyncio.to_thread(
                storage.download_to_path,
                bucket=settings.object_storage_bucket,
                key=file.storage_key,
                destination=path,
                max_bytes=settings.video_provider_max_download_bytes,
            )
        except ObjectStorageError as exc:
            raise VideoGenerationFailure("VIDEO_FILE_UNAVAILABLE") from exc
        if (
            metadata.media_type != file.mime_type
            or metadata.size_bytes != file.size_bytes
            or metadata.sha256 != file.sha256
        ):
            raise VideoGenerationFailure("VIDEO_FILE_INVALID")
        try:
            probe = await asyncio.to_thread(probe_mp4, path)
        except VideoProbeError as exc:
            raise VideoGenerationFailure("VIDEO_FILE_INVALID") from exc
    if not 5.5 <= probe.duration_seconds <= 6.5:
        raise VideoGenerationFailure("VIDEO_DURATION_INVALID")
    return metadata, probe


def _promote_validated_file(
    file: GeneratedFileFact,
    *,
    result_scope: VideoResultScope,
    storage: ObjectStorage,
    settings: Settings,
) -> tuple[GeneratedFileFact, ObjectMetadata]:
    store = ObjectStorageVideoResultStore(
        storage,
        bucket=settings.object_storage_bucket,
        max_bytes=settings.video_provider_max_download_bytes,
    )
    try:
        promoted = store.promote(
            staged=StoredVideoFile(
                storage_key=file.storage_key,
                sha256=file.sha256,
                size_bytes=file.size_bytes,
                mime_type=file.mime_type,
            ),
            scope=result_scope,
        )
        final_metadata = storage.stat(
            bucket=settings.object_storage_bucket,
            key=promoted.storage_key,
        )
    except ObjectStorageError as exc:
        raise VideoGenerationFailure("VIDEO_FILE_UNAVAILABLE") from exc
    except OSError as exc:
        raise VideoGenerationFailure("VIDEO_FILE_INVALID") from exc
    return (
        GeneratedFileFact(
            storage_key=promoted.storage_key,
            sha256=promoted.sha256,
            size_bytes=promoted.size_bytes,
            mime_type=promoted.mime_type,
            duration_seconds=file.duration_seconds,
        ),
        final_metadata,
    )


async def _cancel_provider(
    gateway: ModelGateway,
    result: VideoGatewayResult,
    routing: VideoGenerationJobRouting,
    job_id: UUID,
    audit_context: ModelAuditContext,
) -> None:
    if result.provider_task_id is None:
        return
    try:
        await gateway.cancel_video(
            VideoPollRequest(
                capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
                request_id=f"video-job:{job_id}:cancel",
                provider_task_id=result.provider_task_id,
                result_scope=_video_result_scope(routing, job_id),
            ),
            audit_context=audit_context,
        )
    except ModelGatewayError:
        pass


def _cancel_requested(factory: sessionmaker[Session], job_id: UUID) -> bool:
    with factory() as session:
        return GenerationJobRoutingReader(session).video_cancel_requested(job_id)


def _uuid_fact(payload: dict[str, object], key: str) -> UUID:
    try:
        return UUID(str(payload[key]))
    except (KeyError, TypeError, ValueError) as exc:
        raise VideoGenerationFailure("VIDEO_INPUTS_INVALID") from exc


def _video_result_scope(
    routing: VideoGenerationJobRouting,
    job_id: UUID,
) -> VideoResultScope:
    return VideoResultScope(
        organization_id=routing.organization_id,
        project_id=routing.project_id,
        lesson_unit_id=routing.lesson_unit_id,
        generation_job_id=job_id,
    )
