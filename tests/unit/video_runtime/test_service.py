from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.api.model_gateway.contracts import (
    GeneratedFileFact,
    MediaReference,
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    ModelUsage,
    RouteDecision,
    VideoGatewayResult,
    VideoOperationStatus,
)
from apps.api.video_runtime.contracts import (
    PreparedVideoRuntime,
    ValidatedVideoFile,
    VideoRuntimeError,
    VideoRuntimeResult,
)
from apps.api.video_runtime.service import VideoRuntimeService


def _prepared(*, provider_task_id: str | None = None) -> PreparedVideoRuntime:
    organization_id = uuid4()
    project_id = uuid4()
    node_run_id = uuid4()
    generation_job_id = uuid4()
    return PreparedVideoRuntime(
        node_run_id=node_run_id,
        generation_job_id=generation_job_id,
        organization_id=organization_id,
        project_id=project_id,
        lesson_unit_id=uuid4(),
        creation_item_id=uuid4(),
        audit_context=ModelAuditContext(
            organization_id=organization_id,
            user_id=uuid4(),
            project_id=project_id,
            node_run_id=node_run_id,
            generation_job_id=generation_job_id,
        ),
        prompt=(
            "依据exact IntroSelection生成课堂导入短片；"
            "style=style.primary_math.paper_clay；不得提前讲授。"
        ),
        keyframe=MediaReference(file_version_id=uuid4(), mime_type="image/png"),
        duration_seconds=6,
        provider_task_id=provider_task_id,
    )


def _gateway_result(
    status: VideoOperationStatus,
    *,
    task_id: str = "provider-task",
    file: GeneratedFileFact | None = None,
) -> VideoGatewayResult:
    return VideoGatewayResult(
        request_id="gateway-result",
        status=status,
        route=RouteDecision(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            provider="fake-video",
            model="fake-video-v1",
            reason="configured_route",
        ),
        provider_request_id="provider-request",
        provider_task_id=task_id,
        actual_model="fake-video-v1",
        files=[file] if file is not None else [],
        usage=ModelUsage(output_units={"video_seconds": 6}, cost=Decimal("0")),
        latency_ms=1,
    )


def _file() -> GeneratedFileFact:
    return GeneratedFileFact(
        storage_key="video-runtime/org/project/node/result.mp4",
        sha256="a" * 64,
        size_bytes=4096,
        mime_type="video/mp4",
        width=1280,
        height=720,
        duration_seconds=6,
    )


class FakeTransactions:
    def __init__(self, prepared: PreparedVideoRuntime) -> None:
        self.prepared = prepared
        self.pending_calls: list[VideoGatewayResult] = []
        self.completed_calls: list[tuple[VideoGatewayResult, ValidatedVideoFile]] = []
        self.failures: list[str] = []
        self.raise_on_complete = False

    @contextmanager
    def begin(self):
        yield self

    def prepare_start(self, node_run_id, keyframe_file_version_id, request_id):
        assert node_run_id == self.prepared.node_run_id
        assert keyframe_file_version_id == self.prepared.keyframe.file_version_id
        assert request_id == "video-start"
        return self.prepared

    def prepare_poll(self, node_run_id, request_id):
        assert node_run_id == self.prepared.node_run_id
        assert request_id == "video-poll"
        return self.prepared

    def record_pending(self, prepared, gateway_result):
        assert prepared == self.prepared
        self.pending_calls.append(gateway_result)
        return VideoRuntimeResult(
            node_run_id=prepared.node_run_id,
            generation_job_id=prepared.generation_job_id,
            status=(
                "submitted"
                if gateway_result.status is VideoOperationStatus.SUBMITTED
                else "processing"
            ),
            generation_result_id=None,
            file_asset_version_id=None,
        )

    def complete(self, prepared, gateway_result, validated_file):
        if self.raise_on_complete:
            raise RuntimeError("simulated commit rollback")
        self.completed_calls.append((gateway_result, validated_file))
        return VideoRuntimeResult(
            node_run_id=prepared.node_run_id,
            generation_job_id=prepared.generation_job_id,
            status="completed",
            generation_result_id=uuid4(),
            file_asset_version_id=uuid4(),
        )

    def terminalize_failure(self, prepared, *, code):
        assert prepared == self.prepared
        self.failures.append(code)


class FakeGateway:
    def __init__(self, result: VideoGatewayResult | Exception) -> None:
        self.result = result
        self.requests = []

    async def submit_video(self, request, **kwargs):
        self.requests.append(("submit", request, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    async def poll_video(self, request, **kwargs):
        self.requests.append(("poll", request, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeValidator:
    def __init__(self, result: ValidatedVideoFile | Exception) -> None:
        self.result = result
        self.files: list[GeneratedFileFact] = []

    def validate(self, file: GeneratedFileFact) -> ValidatedVideoFile:
        self.files.append(file)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _validated(file: GeneratedFileFact) -> ValidatedVideoFile:
    return ValidatedVideoFile(
        storage_bucket="course-assets",
        storage_key=file.storage_key,
        etag="etag",
        mime_type=file.mime_type,
        size_bytes=file.size_bytes,
        sha256=file.sha256,
        width=1280,
        height=720,
        duration_ms=6042,
    )


@pytest.mark.asyncio
async def test_start_submits_one_exact_keyframe_without_creating_a_candidate() -> None:
    prepared = _prepared()
    transactions = FakeTransactions(prepared)
    gateway = FakeGateway(_gateway_result(VideoOperationStatus.SUBMITTED))
    validator = FakeValidator(AssertionError("pending output must not be validated"))
    service = VideoRuntimeService(transactions, gateway, validator)

    result = await service.start(
        prepared.node_run_id,
        keyframe_file_version_id=prepared.keyframe.file_version_id,
        request_id="video-start",
    )

    assert result.status == "submitted"
    assert result.generation_result_id is None
    assert transactions.completed_calls == []
    assert validator.files == []
    _, request, kwargs = gateway.requests[0]
    assert request.duration_seconds == 6
    assert request.references == [prepared.keyframe]
    assert "style.primary_math.paper_clay" in request.prompt
    assert kwargs["audit_context"] == prepared.audit_context
    assert kwargs["media_organization_id"] == prepared.organization_id


@pytest.mark.asyncio
async def test_poll_creates_one_candidate_but_never_an_adoption() -> None:
    prepared = _prepared(provider_task_id="provider-task")
    file = _file()
    validated = _validated(file)
    transactions = FakeTransactions(prepared)
    gateway = FakeGateway(_gateway_result(VideoOperationStatus.SUCCEEDED, file=file))
    service = VideoRuntimeService(transactions, gateway, FakeValidator(validated))

    result = await service.poll(prepared.node_run_id, request_id="video-poll")

    assert result.status == "completed"
    assert result.generation_result_id is not None
    assert result.file_asset_version_id is not None
    assert len(transactions.completed_calls) == 1
    assert not hasattr(result, "adoption_id")


@pytest.mark.asyncio
async def test_provider_failure_terminalizes_without_a_candidate() -> None:
    prepared = _prepared()
    transactions = FakeTransactions(prepared)
    gateway = FakeGateway(_gateway_result(VideoOperationStatus.FAILED))
    service = VideoRuntimeService(
        transactions,
        gateway,
        FakeValidator(AssertionError("failed output must not be validated")),
    )

    with pytest.raises(VideoRuntimeError, match="video provider failed") as caught:
        await service.start(
            prepared.node_run_id,
            keyframe_file_version_id=prepared.keyframe.file_version_id,
            request_id="video-start",
        )

    assert caught.value.code == "VIDEO_RUNTIME_PROVIDER_FAILED"
    assert transactions.failures == ["VIDEO_RUNTIME_PROVIDER_FAILED"]
    assert transactions.completed_calls == []


@pytest.mark.asyncio
async def test_file_fact_mismatch_terminalizes_and_complete_rollback_is_not_hidden() -> None:
    prepared = _prepared(provider_task_id="provider-task")
    file = _file()
    transactions = FakeTransactions(prepared)
    validator_error = VideoRuntimeError(
        "VIDEO_RUNTIME_FILE_FACT_MISMATCH",
        "generated video file facts do not match storage",
    )
    service = VideoRuntimeService(
        transactions,
        FakeGateway(_gateway_result(VideoOperationStatus.SUCCEEDED, file=file)),
        FakeValidator(validator_error),
    )

    with pytest.raises(VideoRuntimeError) as caught:
        await service.poll(prepared.node_run_id, request_id="video-poll")

    assert caught.value.code == "VIDEO_RUNTIME_FILE_FACT_MISMATCH"
    assert transactions.failures == ["VIDEO_RUNTIME_FILE_FACT_MISMATCH"]

    transactions = FakeTransactions(replace(prepared))
    transactions.raise_on_complete = True
    service = VideoRuntimeService(
        transactions,
        FakeGateway(_gateway_result(VideoOperationStatus.SUCCEEDED, file=file)),
        FakeValidator(_validated(file)),
    )
    with pytest.raises(VideoRuntimeError) as rollback:
        await service.poll(prepared.node_run_id, request_id="video-poll")

    assert rollback.value.code == "VIDEO_RUNTIME_COMMIT_FAILED"
    assert transactions.failures == ["VIDEO_RUNTIME_COMMIT_FAILED"]
