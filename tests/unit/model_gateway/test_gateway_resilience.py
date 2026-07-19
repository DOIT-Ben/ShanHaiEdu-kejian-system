from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import cast
from uuid import UUID

import pytest

from apps.api.model_gateway.audit import AttemptRequestAudit, AttemptSuccessAudit
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ImageModelRequest,
    ImageProviderResult,
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    ModelUsage,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
    VideoProviderResult,
)
from apps.api.model_gateway.fake import (
    DeterministicFakeImageProvider,
    DeterministicFakeVideoProvider,
    FakeVideoScenario,
)
from apps.api.model_gateway.gateway import ModelGateway


def image_request(*, request_id: str = "req-resilient-image") -> ImageModelRequest:
    return ImageModelRequest(
        capability=ModelCapability.IMAGE_GENERATE_EDUCATION_16X9,
        request_id=request_id,
        prompt="PRIVATE_RESILIENCE_IMAGE_PROMPT",
        width=1280,
        height=720,
    )


def video_request() -> VideoModelRequest:
    return VideoModelRequest(
        capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
        request_id="req-resilient-video",
        prompt="PRIVATE_RESILIENCE_VIDEO_PROMPT",
        duration_seconds=8,
        references=[],
    )


def audit_context() -> ModelAuditContext:
    return ModelAuditContext(
        organization_id=UUID("01980000-0000-7000-8000-000000000010"),
        user_id=UUID("01980000-0000-7000-8000-000000000011"),
        project_id=UUID("01980000-0000-7000-8000-000000000012"),
        node_run_id=UUID("01980000-0000-7000-8000-000000000013"),
        generation_job_id=None,
    )


class RecordingAuditSink:
    attempt_id = UUID("01980000-0000-7000-8000-000000000001")

    def __init__(self, *, fail_success: bool = False, fail_failure: bool = False) -> None:
        self.events: list[object] = []
        self._fail_success = fail_success
        self._fail_failure = fail_failure

    def start(
        self,
        context: ModelAuditContext,
        request: AttemptRequestAudit,
        *,
        provider_name: str | None,
        provider_model: str | None,
        route_reason: str,
    ) -> UUID:
        self.events.append(
            (
                "start",
                context,
                asdict(request),
                provider_name,
                provider_model,
                route_reason,
            )
        )
        return self.attempt_id

    def succeed(
        self,
        attempt_id: UUID,
        context: ModelAuditContext,
        result: AttemptSuccessAudit,
        *,
        latency_ms: int,
    ) -> None:
        if self._fail_success:
            raise RuntimeError("private audit persistence failure")
        self.events.append(("succeed", attempt_id, context, result, latency_ms))

    def fail(
        self,
        attempt_id: UUID,
        context: ModelAuditContext,
        error: ModelGatewayError,
        *,
        latency_ms: int,
    ) -> None:
        if self._fail_failure:
            raise RuntimeError("private audit failure persistence failure")
        self.events.append(("fail", attempt_id, context, error.code, latency_ms))


class InvalidImageProvider:
    provider_name = "invalid-image-provider"
    model_name = "invalid-image-model"

    async def generate(self, request: ImageModelRequest) -> ImageProviderResult:
        del request
        return cast(ImageProviderResult, {"raw_provider_response": "PRIVATE_RAW_RESPONSE"})


class InvalidConstructedImageProvider:
    provider_name = "invalid-constructed-image-provider"
    model_name = "invalid-constructed-image-model"

    async def generate(self, request: ImageModelRequest) -> ImageProviderResult:
        del request
        return ImageProviderResult.model_construct(
            provider_request_id="invalid-constructed-request",
            actual_model=self.model_name,
            files=[],
            usage=ModelUsage(),
        )


class CancellableImageProvider:
    provider_name = "cancellable-image-provider"
    model_name = "cancellable-image-model"

    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def generate(self, request: ImageModelRequest) -> ImageProviderResult:
        del request
        self.started.set()
        await asyncio.Future[None]()
        raise AssertionError("unreachable")


class ReturnedUnknownVideoProvider(DeterministicFakeVideoProvider):
    async def submit(self, request: VideoModelRequest) -> VideoProviderResult:
        self.submit_calls += 1
        return VideoProviderResult(
            status=VideoOperationStatus.SUBMISSION_UNKNOWN,
            provider_request_id=f"fake:{request.request_id}",
            provider_task_id=None,
            actual_model=self.model_name,
            files=[],
            usage=ModelUsage(),
        )


async def test_invalid_provider_result_is_normalized_and_closes_attempt() -> None:
    sink = RecordingAuditSink()
    gateway = ModelGateway(
        {},
        image_routes={ModelCapability.IMAGE_GENERATE_EDUCATION_16X9: InvalidImageProvider()},
        audit_sink=sink,
    )

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.generate_image(image_request(), audit_context=audit_context())

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE
    assert captured.value.retryable is False
    assert [event[0] for event in sink.events] == ["start", "fail"]
    assert "PRIVATE_RAW_RESPONSE" not in repr(sink.events)


async def test_invalid_constructed_provider_result_is_revalidated_before_audit() -> None:
    sink = RecordingAuditSink()
    gateway = ModelGateway(
        {},
        image_routes={
            ModelCapability.IMAGE_GENERATE_EDUCATION_16X9: InvalidConstructedImageProvider()
        },
        audit_sink=sink,
    )

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.generate_image(image_request(), audit_context=audit_context())

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE
    assert captured.value.retryable is False
    assert [event[0] for event in sink.events] == ["start", "fail"]


async def test_returned_submission_unknown_is_failed_and_never_retried() -> None:
    provider = ReturnedUnknownVideoProvider(FakeVideoScenario.SUBMISSION_UNKNOWN)
    sink = RecordingAuditSink()
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        audit_sink=sink,
    )

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.submit_video(video_request(), audit_context=audit_context())

    assert captured.value.code == GatewayErrorCode.SUBMISSION_UNKNOWN
    assert captured.value.retryable is False
    assert provider.submit_calls == 1
    assert [event[0] for event in sink.events] == ["start", "fail"]


async def test_video_audit_failure_becomes_non_retryable_unknown_submission() -> None:
    provider = DeterministicFakeVideoProvider()
    sink = RecordingAuditSink(fail_success=True)
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        audit_sink=sink,
    )

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.submit_video(video_request(), audit_context=audit_context())

    assert captured.value.code == GatewayErrorCode.SUBMISSION_UNKNOWN
    assert captured.value.retryable is False
    assert captured.value.__cause__ is None
    assert provider.submit_calls == 1
    assert [event[0] for event in sink.events] == ["start", "fail"]


async def test_unknown_submission_survives_failure_audit_outage() -> None:
    provider = ReturnedUnknownVideoProvider(FakeVideoScenario.SUBMISSION_UNKNOWN)
    sink = RecordingAuditSink(fail_failure=True)
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        audit_sink=sink,
    )

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.submit_video(video_request(), audit_context=audit_context())

    assert captured.value.code == GatewayErrorCode.SUBMISSION_UNKNOWN
    assert captured.value.retryable is False
    assert captured.value.__cause__ is None
    assert provider.submit_calls == 1


async def test_thrown_unknown_submission_survives_failure_audit_outage() -> None:
    provider = DeterministicFakeVideoProvider(FakeVideoScenario.SUBMISSION_UNKNOWN)
    sink = RecordingAuditSink(fail_failure=True)
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        audit_sink=sink,
    )

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.submit_video(video_request(), audit_context=audit_context())

    assert captured.value.code == GatewayErrorCode.SUBMISSION_UNKNOWN
    assert captured.value.retryable is False
    assert provider.submit_calls == 1


async def test_poll_audit_outage_is_not_reported_as_unknown_submission() -> None:
    provider = DeterministicFakeVideoProvider()
    submit_gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
    )
    submitted = await submit_gateway.submit_video(video_request())
    assert submitted.provider_task_id is not None
    poll_gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        audit_sink=RecordingAuditSink(fail_success=True),
    )

    with pytest.raises(ModelGatewayError) as captured:
        await poll_gateway.poll_video(
            VideoPollRequest(
                capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
                request_id="req-resilient-video-poll",
                provider_task_id=submitted.provider_task_id,
            ),
            audit_context=audit_context(),
        )

    assert captured.value.code == GatewayErrorCode.AUDIT_UNAVAILABLE
    assert captured.value.retryable is False


async def test_asyncio_task_cancellation_uses_stable_error_and_closes_attempt() -> None:
    provider = CancellableImageProvider()
    sink = RecordingAuditSink()
    gateway = ModelGateway(
        {},
        image_routes={ModelCapability.IMAGE_GENERATE_EDUCATION_16X9: provider},
        audit_sink=sink,
    )
    task = asyncio.create_task(
        gateway.generate_image(image_request(), audit_context=audit_context())
    )
    await provider.started.wait()

    task.cancel()
    with pytest.raises(ModelGatewayError) as captured:
        await task

    assert captured.value.code == GatewayErrorCode.CANCELLED
    assert captured.value.retryable is False
    assert [event[0] for event in sink.events] == ["start", "fail"]


async def test_fake_storage_keys_are_safe_for_every_valid_request_id() -> None:
    gateway = ModelGateway(
        {},
        image_routes={
            ModelCapability.IMAGE_GENERATE_EDUCATION_16X9: DeterministicFakeImageProvider()
        },
    )

    result = await gateway.generate_image(image_request(request_id="../valid-contract-id"))

    assert ".." not in result.files[0].storage_key
    assert "valid-contract-id" not in result.files[0].storage_key


async def test_success_logs_hash_provider_handles_instead_of_recording_raw_ids(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def capture(_message: str, *, extra: dict[str, object]) -> None:
        captured.update(extra)

    monkeypatch.setattr("apps.api.model_gateway.telemetry.logger.info", capture)
    provider = DeterministicFakeVideoProvider()
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
    )

    result = await gateway.submit_video(video_request())

    rendered = repr(captured)
    assert result.provider_request_id not in rendered
    assert result.provider_task_id not in rendered
    assert captured["provider_request_hash"]
    assert captured["provider_task_hash"]
