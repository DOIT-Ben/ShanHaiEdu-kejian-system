from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from apps.api.assets.models import FileAssetVersion
from apps.api.creation.models import CreationItem, GenerationResult
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import system_actor
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.service import GenerationJobService
from apps.api.main import create_app
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt
from apps.api.model_gateway.contracts import (
    GeneratedFileFact,
    ModelCapability,
    ModelUsage,
    VideoGatewayResult,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
    VideoProviderResult,
)
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.settings import Settings
from apps.api.uploads.storage import ObjectStorage
from apps.api.workflows.models import NodeRun
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.identity import override_test_identity
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.video_golden_slice_support import seed_video_project
from workers import video_generation as video_worker
from workers.video_generation import execute_video_generation_job
from workers.video_generation_persistence import ValidatedVideo
from workflow.node_state import NodeStatus


class StoredVideoFakeProvider:
    provider_name = "deterministic-fake"
    model_name = "fake-video-6s-v1"

    def __init__(
        self,
        storage: FakeObjectStorage,
        payload: bytes,
        *,
        invalid_media: bool = False,
    ) -> None:
        self._storage = storage
        self._payload = payload
        self._invalid_media = invalid_media
        self.poll_calls = 0
        self.submitted_prompt: str | None = None

    async def submit(
        self,
        request: VideoModelRequest,
        *,
        organization_id: UUID | None = None,
    ) -> VideoProviderResult:
        assert organization_id is not None
        assert request.duration_seconds == 6
        assert len(request.references) == 1
        self.submitted_prompt = request.prompt
        return self._result(request.request_id, VideoOperationStatus.SUBMITTED)

    async def poll(self, request: VideoPollRequest) -> VideoProviderResult:
        self.poll_calls += 1
        if self.poll_calls == 1:
            return self._result(request.request_id, VideoOperationStatus.POLLING)
        key = "fake/video-golden-slice/result.mp4"
        payload = b"not-an-mp4" if self._invalid_media else self._payload
        metadata = self._storage.put_bytes(
            bucket="shanhaiedu",
            key=key,
            payload=payload,
            media_type="video/mp4",
        )
        return VideoProviderResult(
            status=VideoOperationStatus.SUCCEEDED,
            provider_request_id=f"fake:{request.request_id}",
            provider_task_id="fake-video-task",
            actual_model=self.model_name,
            files=[
                GeneratedFileFact(
                    storage_key=key,
                    sha256=metadata.sha256 or "",
                    size_bytes=metadata.size_bytes,
                    mime_type="video/mp4",
                    duration_seconds=6,
                )
            ],
            usage=ModelUsage(output_units={"video_seconds": 6}),
        )

    async def cancel(self, request: VideoPollRequest) -> VideoProviderResult:
        return self._result(request.request_id, VideoOperationStatus.CANCELLED)

    def _result(
        self,
        request_id: str,
        status: VideoOperationStatus,
    ) -> VideoProviderResult:
        return VideoProviderResult(
            status=status,
            provider_request_id=f"fake:{request_id}",
            provider_task_id="fake-video-task",
            actual_model=self.model_name,
            usage=ModelUsage(),
        )


def test_video_worker_lease_covers_provider_and_validation_windows() -> None:
    settings = _settings("postgresql://example.invalid/test").model_copy(
        update={
            "worker_lease_seconds": 5,
            "video_provider_timeout_seconds": 120,
            "video_provider_poll_seconds": 0.01,
            "video_provider_max_wait_seconds": 10,
        }
    )

    assert video_worker._video_lease_seconds(settings) == 551


async def test_video_worker_persists_verified_candidate_and_refreshes_playback(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    storage = FakeObjectStorage()
    payload = _six_second_mp4(tmp_path)
    provider = StoredVideoFakeProvider(storage, payload)
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    settings = _settings(migrated_database_url).model_copy(
        update={"worker_lease_seconds": 5, "video_provider_max_wait_seconds": 10}
    )
    claimed_lease_seconds: list[int] = []
    original_claim = GenerationJobService.claim

    def recording_claim(
        service: GenerationJobService,
        job_id: UUID,
        *,
        worker_id: str,
        lease_seconds: int,
    ):
        claimed_lease_seconds.append(lease_seconds)
        return original_claim(
            service,
            job_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )

    monkeypatch.setattr(GenerationJobService, "claim", recording_claim)
    app = create_app(settings=settings, session_factory=factory, object_storage=storage)
    override_test_identity(app, seeded.actor)
    lesson = seeded.lessons[0]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            started = await client.post(
                f"/api/v2/projects/{seeded.project_id}/lessons/{lesson.lesson_id}"
                "/video/generations",
                headers={"Idempotency-Key": "video-worker-success"},
                json={"keyframe_file_asset_version_id": str(lesson.keyframe_file_version_id)},
            )
            assert started.status_code == 202, started.text
            job_id = UUID(started.json()["data"]["job_id"])
            outcome = await execute_video_generation_job(
                job_id,
                worker_id="video-worker-success",
                gateway=gateway,
                storage=storage,
                settings=settings,
            )
            duplicate = await execute_video_generation_job(
                job_id,
                worker_id="video-worker-duplicate",
                gateway=gateway,
                storage=storage,
                settings=settings,
            )
            assert outcome == "succeeded"
            assert duplicate == "ignored"
            snapshot = await client.get(
                f"/api/v2/projects/{seeded.project_id}/lessons/{lesson.lesson_id}/video"
            )
            assert snapshot.status_code == 200, snapshot.text
            playback_url = snapshot.json()["data"]["candidate"]["playback_url"]
            playback = await client.get(playback_url)
            storage.put_bytes(
                bucket="shanhaiedu",
                key="fake/video-golden-slice/result.mp4",
                payload=b"mutated-after-verification",
                media_type="video/mp4",
            )
            drifted_playback = await client.get(playback_url)
        assert claimed_lease_seconds == [551]
        assert provider.submitted_prompt is not None
        assert "intro_selection.snapshot" in provider.submitted_prompt
        assert str(lesson.intro_selection_id) in provider.submitted_prompt
        assert str(lesson.intro_artifact_version_id) in provider.submitted_prompt
        assert playback.status_code == 200
        assert playback.headers["content-type"] == "video/mp4"
        assert playback.content == payload
        assert drifted_playback.status_code == 409
        assert drifted_playback.json()["error"]["code"] == "VIDEO_FILE_FACT_MISMATCH"
        assert snapshot.json()["data"]["candidate"] == {
            "result_id": snapshot.json()["data"]["candidate"]["result_id"],
            "file_asset_version_id": snapshot.json()["data"]["candidate"]["file_asset_version_id"],
            "mime_type": "video/mp4",
            "byte_size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "duration_ms": 6000,
            "playback_url": playback_url,
            "adoption_id": None,
            "saved_binding_id": None,
        }
        with factory() as session:
            job = session.get(GenerationJob, job_id)
            node = session.get(NodeRun, job.node_run_id if job else None)
            result_count = session.scalar(
                select(func.count())
                .select_from(GenerationResult)
                .where(GenerationResult.generation_job_id == job_id)
            )
            attempts = list(
                session.scalars(
                    select(GenerationAttempt)
                    .where(GenerationAttempt.generation_job_id == job_id)
                    .order_by(GenerationAttempt.attempt_no)
                )
            )
        assert job is not None and job.status == "succeeded"
        assert node is not None and node.status == "review_required"
        assert result_count == 1
        assert [attempt.status for attempt in attempts] == ["succeeded"] * 3
    finally:
        engine.dispose()


async def test_video_worker_synchronizes_pre_execution_cancellation_without_provider(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    storage = FakeObjectStorage()
    provider = StoredVideoFakeProvider(storage, _six_second_mp4(tmp_path))
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    settings = _settings(migrated_database_url)
    app = create_app(settings=settings, session_factory=factory, object_storage=storage)
    override_test_identity(app, seeded.actor)
    lesson = seeded.lessons[0]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            started = await client.post(
                f"/api/v2/projects/{seeded.project_id}/lessons/{lesson.lesson_id}"
                "/video/generations",
                headers={"Idempotency-Key": "video-worker-cancel-start"},
                json={"keyframe_file_asset_version_id": str(lesson.keyframe_file_version_id)},
            )
            assert started.status_code == 202, started.text
            job_id = UUID(started.json()["data"]["job_id"])
            cancelled = await client.post(
                f"/api/v2/generation-jobs/{job_id}/cancel",
                headers={"Idempotency-Key": "video-worker-cancel-job"},
            )
        assert cancelled.status_code == 202, cancelled.text
        outcome = await execute_video_generation_job(
            job_id,
            worker_id="video-worker-cancelled",
            gateway=gateway,
            storage=storage,
            settings=settings,
        )
        with factory() as session:
            job = session.get(GenerationJob, job_id)
            node = session.get(NodeRun, job.node_run_id if job else None)
            result_count = session.scalar(
                select(func.count())
                .select_from(GenerationResult)
                .where(GenerationResult.generation_job_id == job_id)
            )
        assert outcome == "cancelled"
        assert provider.poll_calls == 0
        assert job is not None and job.status == "cancelled"
        assert node is not None and node.status == "cancelled"
        assert result_count == 0
    finally:
        engine.dispose()


async def test_video_worker_finalizes_cancellation_after_media_validation(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    storage = FakeObjectStorage()
    provider = StoredVideoFakeProvider(storage, _six_second_mp4(tmp_path))
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    settings = _settings(migrated_database_url)
    app = create_app(settings=settings, session_factory=factory, object_storage=storage)
    override_test_identity(app, seeded.actor)
    lesson = seeded.lessons[0]
    original_validate = video_worker.validate_video_result
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            started = await client.post(
                f"/api/v2/projects/{seeded.project_id}/lessons/{lesson.lesson_id}"
                "/video/generations",
                headers={"Idempotency-Key": "video-worker-late-cancel-start"},
                json={"keyframe_file_asset_version_id": str(lesson.keyframe_file_version_id)},
            )
            assert started.status_code == 202, started.text
            job_id = UUID(started.json()["data"]["job_id"])

            async def validate_then_cancel(
                result: VideoGatewayResult,
                *,
                storage: ObjectStorage,
                settings: Settings,
            ) -> ValidatedVideo:
                validated = await original_validate(result, storage=storage, settings=settings)
                cancelled = await client.post(
                    f"/api/v2/generation-jobs/{job_id}/cancel",
                    headers={"Idempotency-Key": "video-worker-late-cancel-job"},
                )
                assert cancelled.status_code == 202, cancelled.text
                return validated

            monkeypatch.setattr(video_worker, "validate_video_result", validate_then_cancel)
            outcome = await execute_video_generation_job(
                job_id,
                worker_id="video-worker-late-cancel",
                gateway=gateway,
                storage=storage,
                settings=settings,
            )

        with factory() as session:
            job = session.get(GenerationJob, job_id)
            assert job is not None and job.creation_batch_id is not None
            node = session.get(NodeRun, job.node_run_id)
            item = session.scalar(
                select(CreationItem).where(CreationItem.creation_batch_id == job.creation_batch_id)
            )
            result_count = session.scalar(
                select(func.count())
                .select_from(GenerationResult)
                .where(GenerationResult.generation_job_id == job_id)
            )
        assert outcome == "cancelled"
        assert job.status == "cancelled"
        assert node is not None and node.status == "cancelled"
        assert item is not None and item.status == "ready"
        assert result_count == 0
    finally:
        engine.dispose()


async def test_video_worker_does_not_cancel_job_leased_by_another_worker(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    storage = FakeObjectStorage()
    provider = StoredVideoFakeProvider(storage, _six_second_mp4(tmp_path))
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    settings = _settings(migrated_database_url)
    app = create_app(settings=settings, session_factory=factory, object_storage=storage)
    override_test_identity(app, seeded.actor)
    lesson = seeded.lessons[0]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            started = await client.post(
                f"/api/v2/projects/{seeded.project_id}/lessons/{lesson.lesson_id}"
                "/video/generations",
                headers={"Idempotency-Key": "video-worker-lease-start"},
                json={"keyframe_file_asset_version_id": str(lesson.keyframe_file_version_id)},
            )
        assert started.status_code == 202, started.text
        job_id = UUID(started.json()["data"]["job_id"])
        actor = system_actor(seeded.actor.organization_id)
        with factory() as session, session.begin():
            claimed = GenerationJobService(
                session,
                actor=actor,
                idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
            ).claim(job_id, worker_id="video-worker-owner", lease_seconds=60)
            assert claimed is not None and claimed.node_run_id is not None
            WorkflowRuntimeService(session, actor).transition_node(
                claimed.node_run_id,
                NodeStatus.RUNNING,
            )

        outcome = await execute_video_generation_job(
            job_id,
            worker_id="video-worker-competitor",
            gateway=gateway,
            storage=storage,
            settings=settings,
        )
        with factory() as session:
            job = session.get(GenerationJob, job_id)
            node = session.get(NodeRun, job.node_run_id if job else None)
        assert outcome == "ignored"
        assert provider.poll_calls == 0
        assert job is not None and job.status == "running"
        assert job.lease_owner == "video-worker-owner"
        assert node is not None and node.status == "running"
    finally:
        engine.dispose()


async def test_video_worker_rejects_invalid_mp4_without_candidate(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    storage = FakeObjectStorage()
    provider = StoredVideoFakeProvider(
        storage,
        _six_second_mp4(tmp_path),
        invalid_media=True,
    )
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    settings = _settings(migrated_database_url)
    app = create_app(settings=settings, session_factory=factory, object_storage=storage)
    override_test_identity(app, seeded.actor)
    lesson = seeded.lessons[0]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            started = await client.post(
                f"/api/v2/projects/{seeded.project_id}/lessons/{lesson.lesson_id}"
                "/video/generations",
                headers={"Idempotency-Key": "video-worker-invalid"},
                json={"keyframe_file_asset_version_id": str(lesson.keyframe_file_version_id)},
            )
        assert started.status_code == 202, started.text
        job_id = UUID(started.json()["data"]["job_id"])
        outcome = await execute_video_generation_job(
            job_id,
            worker_id="video-worker-invalid",
            gateway=gateway,
            storage=storage,
            settings=settings,
        )
        with factory() as session:
            job = session.get(GenerationJob, job_id)
            node = session.get(NodeRun, job.node_run_id if job else None)
            result_count = session.scalar(
                select(func.count())
                .select_from(GenerationResult)
                .where(GenerationResult.generation_job_id == job_id)
            )
            version_count = session.scalar(
                select(func.count())
                .select_from(FileAssetVersion)
                .where(FileAssetVersion.metadata_json["generation_job_id"].astext == str(job_id))
            )
        assert outcome == "failed"
        assert job is not None and job.status == "failed"
        assert job.error_code == "VIDEO_FILE_INVALID"
        assert node is not None and node.status == "failed"
        assert result_count == 0
        assert version_count == 0
    finally:
        engine.dispose()


def _settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=SecretStr(database_url),
        session_access_code=None,
        session_allowed_origins=[],
        session_csrf_secret=None,
        session_teacher_principal_id=None,
        object_storage_bucket="shanhaiedu",
        video_provider_poll_seconds=0.01,
        video_provider_max_wait_seconds=10,
    )


def _six_second_mp4(tmp_path: Path) -> bytes:
    output = tmp_path / "six-second.mp4"
    completed = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x180:d=6:r=12",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-y",
            str(output),
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    return output.read_bytes()
