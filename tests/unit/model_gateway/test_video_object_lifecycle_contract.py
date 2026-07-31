from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

import pytest

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    GeneratedFileFact,
    MediaReference,
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    ModelUsage,
    RouteDecision,
    VideoGatewayResult,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
    VideoProviderResult,
    VideoResultScope,
)
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.model_gateway.object_storage_video_store import (
    ObjectStorageVideoResultStore,
    build_video_final_key,
    build_video_staging_key,
)
from apps.api.model_gateway.video_smoke import VideoProbeResult
from apps.api.settings import Settings
from tests.fakes.object_storage import FakeObjectStorage
from workers.video_generation_runtime import validate_video_result

ORG_ID = UUID("018f0000-0000-7000-8000-000000000101")
PROJECT_ID = UUID("018f0000-0000-7000-8000-000000000102")
LESSON_ID = UUID("018f0000-0000-7000-8000-000000000103")
JOB_ID = UUID("018f0000-0000-7000-8000-000000000104")
TASK_ID = "provider-private-task-must-never-enter-an-object-key"


def scope() -> VideoResultScope:
    return VideoResultScope(
        organization_id=ORG_ID,
        project_id=PROJECT_ID,
        lesson_unit_id=LESSON_ID,
        generation_job_id=JOB_ID,
    )


def test_video_requests_carry_exact_internal_result_scope() -> None:
    result_scope = scope()
    request = VideoModelRequest(
        capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
        request_id="video-job:submit",
        prompt="A paper boat crosses a pond.",
        duration_seconds=6,
        references=[
            MediaReference(
                file_version_id=UUID("018f0000-0000-7000-8000-000000000105"),
                mime_type="image/png",
            )
        ],
        result_scope=result_scope,
    )
    poll = VideoPollRequest(
        capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
        request_id="video-job:poll:1",
        provider_task_id=TASK_ID,
        result_scope=result_scope,
    )

    assert request.result_scope == result_scope
    assert poll.result_scope == result_scope
    assert TASK_ID not in request.model_dump_json()


def test_video_object_keys_are_deterministic_and_redact_provider_task_id() -> None:
    staging = build_video_staging_key(scope(), provider_name="newapi", provider_task_id=TASK_ID)
    same_staging = build_video_staging_key(
        scope(), provider_name="newapi", provider_task_id=TASK_ID
    )
    final = build_video_final_key(scope(), sha256="a" * 64)

    assert staging == same_staging
    assert staging.startswith("staging/video-results/")
    assert final == (
        f"assets/video-results/{ORG_ID}/{PROJECT_ID}/{LESSON_ID}/{JOB_ID}/{'a' * 64}.mp4"
    )
    assert TASK_ID not in staging
    assert TASK_ID not in final
    task_hash = hashlib.sha256(f"newapi\0{TASK_ID}".encode()).hexdigest()[:32]
    assert task_hash in staging


def test_promote_is_idempotent_and_rejects_drifted_destination(tmp_path: Path) -> None:
    storage = FakeObjectStorage()
    store = ObjectStorageVideoResultStore(
        storage,
        bucket="shanhaiedu",
        max_bytes=1024,
    )
    source = tmp_path / "candidate.mp4"
    source.write_bytes(b"validated-mp4")

    staged = store.stage(
        source=source,
        media_type="video/mp4",
        scope=scope(),
        provider_name="newapi",
        provider_task_id=TASK_ID,
    )
    promoted = store.promote(staged=staged, scope=scope())
    repeated = store.promote(staged=staged, scope=scope())

    assert promoted.storage_key == repeated.storage_key
    assert promoted.storage_key.startswith("assets/video-results/")
    assert storage.stat(bucket="shanhaiedu", key=promoted.storage_key).sha256 == promoted.sha256

    storage.put_bytes(
        bucket="shanhaiedu",
        key=promoted.storage_key,
        payload=b"drifted",
        media_type="video/mp4",
    )
    with pytest.raises(OSError, match="promotion destination facts do not match"):
        store.promote(staged=staged, scope=scope())


def test_promote_accepts_concurrent_winner_without_deleting_its_final(
    tmp_path: Path,
) -> None:
    class ConcurrentWinnerStorage(FakeObjectStorage):
        def __init__(self) -> None:
            super().__init__()
            self._race_once = True

        def copy(self, **kwargs):
            if self._race_once:
                self._race_once = False
                super().copy(**kwargs)
                raise ObjectStorageError("concurrent copy lost")
            return super().copy(**kwargs)

    from apps.api.uploads.storage import ObjectStorageError

    storage = ConcurrentWinnerStorage()
    store = ObjectStorageVideoResultStore(storage, bucket="shanhaiedu", max_bytes=1024)
    source = tmp_path / "candidate.mp4"
    source.write_bytes(b"winner-video")
    staged = store.stage(
        source=source,
        media_type="video/mp4",
        scope=scope(),
        provider_name="newapi",
        provider_task_id=TASK_ID,
    )

    promoted = store.promote(staged=staged, scope=scope())

    assert promoted.storage_key.startswith("assets/video-results/")
    assert storage.stat(bucket="shanhaiedu", key=promoted.storage_key).sha256 == staged.sha256


def test_promote_does_not_copy_when_destination_lookup_is_unavailable(tmp_path: Path) -> None:
    from apps.api.uploads.storage import ObjectStorageError

    class LookupFailureStorage(FakeObjectStorage):
        def __init__(self) -> None:
            super().__init__()
            self.copy_calls = 0

        def stat(self, *, bucket: str, key: str):
            if key.startswith("assets/video-results/"):
                raise ObjectStorageError("lookup unavailable")
            return super().stat(bucket=bucket, key=key)

        def copy(self, **kwargs):
            self.copy_calls += 1
            return super().copy(**kwargs)

    storage = LookupFailureStorage()
    store = ObjectStorageVideoResultStore(storage, bucket="shanhaiedu", max_bytes=1024)
    source = tmp_path / "candidate.mp4"
    source.write_bytes(b"validated-mp4")
    staged = store.stage(
        source=source,
        media_type="video/mp4",
        scope=scope(),
        provider_name="newapi",
        provider_task_id=TASK_ID,
    )

    with pytest.raises(OSError, match="video result promotion failed"):
        store.promote(staged=staged, scope=scope())

    assert storage.copy_calls == 0


async def test_gateway_rejects_result_scope_that_does_not_match_audit_context() -> None:
    class Provider:
        provider_name = "deterministic-fake"
        model_name = "fake-video"

        async def submit(self, request: VideoModelRequest, *, organization_id=None):
            return VideoProviderResult(
                status=VideoOperationStatus.SUBMITTED,
                provider_task_id="private-task",
                actual_model="fake-video",
                usage=ModelUsage(),
            )

        async def poll(self, request: VideoPollRequest):
            raise AssertionError("poll must not run")

        async def cancel(self, request: VideoPollRequest):
            raise AssertionError("cancel must not run")

    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: Provider()},
    )
    request = VideoModelRequest(
        capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
        request_id="video-scope-mismatch",
        prompt="animate",
        duration_seconds=6,
        result_scope=scope(),
    )
    audit = ModelAuditContext(
        organization_id=ORG_ID,
        user_id=None,
        project_id=UUID("018f0000-0000-7000-8000-000000000199"),
        node_run_id=UUID("018f0000-0000-7000-8000-000000000198"),
        generation_job_id=JOB_ID,
        lesson_unit_id=LESSON_ID,
    )

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.submit_video(request, audit_context=audit)

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE


@pytest.mark.parametrize("operation", ["submit", "poll", "cancel"])
async def test_gateway_rejects_business_video_audit_without_result_scope(
    operation: str,
) -> None:
    calls: list[str] = []

    class Provider:
        provider_name = "deterministic-fake"
        model_name = "fake-video"

        async def submit(self, request: VideoModelRequest):
            calls.append("submit")
            return VideoProviderResult(
                status=VideoOperationStatus.SUBMITTED,
                provider_task_id="private-task",
                actual_model=self.model_name,
                usage=ModelUsage(),
            )

        async def poll(self, request: VideoPollRequest):
            calls.append("poll")
            return VideoProviderResult(
                status=VideoOperationStatus.POLLING,
                provider_task_id=request.provider_task_id,
                actual_model=self.model_name,
                usage=ModelUsage(),
            )

        async def cancel(self, request: VideoPollRequest):
            calls.append("cancel")
            return VideoProviderResult(
                status=VideoOperationStatus.CANCELLED,
                provider_task_id=request.provider_task_id,
                actual_model=self.model_name,
                usage=ModelUsage(),
            )

    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: Provider()},
    )
    audit = ModelAuditContext(
        organization_id=ORG_ID,
        user_id=None,
        project_id=PROJECT_ID,
        node_run_id=UUID("018f0000-0000-7000-8000-000000000198"),
        generation_job_id=JOB_ID,
        lesson_unit_id=LESSON_ID,
    )
    request = (
        VideoModelRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id="video-business-submit-without-scope",
            prompt="animate",
            duration_seconds=6,
        )
        if operation == "submit"
        else VideoPollRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id=f"video-business-{operation}-without-scope",
            provider_task_id="private-task",
        )
    )

    with pytest.raises(ModelGatewayError) as captured:
        if operation == "submit":
            await gateway.submit_video(request, audit_context=audit)  # type: ignore[arg-type]
        elif operation == "poll":
            await gateway.poll_video(request, audit_context=audit)  # type: ignore[arg-type]
        else:
            await gateway.cancel_video(request, audit_context=audit)  # type: ignore[arg-type]

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE
    assert calls == []


async def test_gateway_allows_scope_less_local_smoke_without_audit() -> None:
    class Provider:
        provider_name = "deterministic-fake"
        model_name = "fake-video"

        async def submit(self, request: VideoModelRequest):
            return VideoProviderResult(
                status=VideoOperationStatus.SUBMITTED,
                provider_task_id="private-task",
                actual_model=self.model_name,
                usage=ModelUsage(),
            )

        async def poll(self, request: VideoPollRequest):
            raise AssertionError("poll must not run")

        async def cancel(self, request: VideoPollRequest):
            raise AssertionError("cancel must not run")

    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: Provider()},
    )

    result = await gateway.submit_video(
        VideoModelRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id="video-local-smoke-without-scope",
            prompt="animate",
            duration_seconds=6,
        )
    )

    assert result.provider_task_id == "private-task"


async def test_worker_promotes_validated_staging_file_before_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = FakeObjectStorage()
    store = ObjectStorageVideoResultStore(storage, bucket="shanhaiedu", max_bytes=1024)
    source = tmp_path / "candidate.mp4"
    source.write_bytes(b"validated-video")
    staged = store.stage(
        source=source,
        media_type="video/mp4",
        scope=scope(),
        provider_name="newapi",
        provider_task_id=TASK_ID,
    )
    monkeypatch.setattr(
        "workers.video_generation_runtime.probe_mp4",
        lambda _path: VideoProbeResult(duration_seconds=6.0, width=320, height=180),
    )
    result = VideoGatewayResult(
        request_id="video-job:poll:1",
        status=VideoOperationStatus.SUCCEEDED,
        route=RouteDecision(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            provider="newapi",
            model="video-grok",
            reason="configured_primary",
        ),
        provider_request_id=None,
        provider_task_id=TASK_ID,
        actual_model="video-grok",
        files=[
            GeneratedFileFact(
                storage_key=staged.storage_key,
                sha256=staged.sha256,
                size_bytes=staged.size_bytes,
                mime_type=staged.mime_type,
                duration_seconds=6,
            )
        ],
        usage=ModelUsage(),
        latency_ms=1,
    )

    validated = await validate_video_result(
        result,
        result_scope=scope(),
        storage=storage,
        settings=Settings(_env_file=None, object_storage_bucket="shanhaiedu"),
    )

    assert validated.file.storage_key.startswith("assets/video-results/")
    assert storage.stat(bucket="shanhaiedu", key=validated.file.storage_key).sha256 == staged.sha256


async def test_real_api_deterministic_video_provider_uses_scoped_staging_key() -> None:
    from tests.e2e.r1_rescue_worker import R1RescueVideoProvider

    storage = FakeObjectStorage()
    provider = R1RescueVideoProvider(storage, bucket="shanhaiedu", payload=b"fake-mp4")
    request = VideoModelRequest(
        capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
        request_id="r1-rescue-submit",
        prompt="animate",
        duration_seconds=6,
        references=[
            MediaReference(
                file_version_id=UUID("018f0000-0000-7000-8000-000000000105"),
                mime_type="image/png",
            )
        ],
        result_scope=scope(),
    )
    submitted = await provider.submit(request, organization_id=ORG_ID)
    polled = await provider.poll(
        VideoPollRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id="r1-rescue-poll",
            provider_task_id=submitted.provider_task_id or "",
            result_scope=scope(),
        )
    )

    assert polled.files[0].storage_key == build_video_staging_key(
        scope(),
        provider_name=provider.provider_name,
        provider_task_id=submitted.provider_task_id or "",
    )
    assert (submitted.provider_task_id or "") not in polled.files[0].storage_key
