"""Deterministic providers for ordinary tests and CI."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    GeneratedFileFact,
    ImageModelRequest,
    ImageProviderResult,
    ModelGatewayError,
    ModelUsage,
    TextModelRequest,
    TextProviderResult,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
    VideoProviderResult,
)


class FakeScenario(StrEnum):
    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"


class FakeVideoScenario(StrEnum):
    SUCCESS = "success"
    SUBMISSION_UNKNOWN = "submission_unknown"
    FAILED = "failed"


def _raise_fake_error(scenario: FakeScenario) -> None:
    errors = {
        FakeScenario.RATE_LIMITED: ModelGatewayError(
            GatewayErrorCode.PROVIDER_RATE_LIMITED,
            retryable=True,
            retry_after_seconds=1,
        ),
        FakeScenario.TIMEOUT: ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True),
        FakeScenario.REJECTED: ModelGatewayError(GatewayErrorCode.REJECTED, retryable=False),
        FakeScenario.UNAVAILABLE: ModelGatewayError(
            GatewayErrorCode.PROVIDER_UNAVAILABLE,
            retryable=True,
        ),
        FakeScenario.CANCELLED: ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False),
    }
    if scenario in errors:
        raise errors[scenario]


class DeterministicFakeTextProvider:
    provider_name = "deterministic-fake"
    model_name = "fake-text-v1"

    def __init__(self, scenario: FakeScenario = FakeScenario.SUCCESS) -> None:
        self._scenario = scenario

    async def complete(self, request: TextModelRequest) -> TextProviderResult:
        _raise_fake_error(self._scenario)
        return TextProviderResult(
            text="SHANHAIEDU_FAKE_SMOKE_OK",
            provider_request_id=f"fake:{request.request_id}",
            actual_model=self.model_name,
            finish_reason="stop",
            usage=ModelUsage(
                prompt_tokens=8,
                completion_tokens=4,
                total_tokens=12,
                cost=Decimal("0"),
            ),
        )


class DeterministicFakeImageProvider:
    provider_name = "deterministic-fake"
    model_name = "fake-image-v1"

    def __init__(self, scenario: FakeScenario = FakeScenario.SUCCESS) -> None:
        self._scenario = scenario

    async def generate(self, request: ImageModelRequest) -> ImageProviderResult:
        _raise_fake_error(self._scenario)
        request_key = _fake_key(request.request_id)
        return ImageProviderResult(
            provider_request_id=f"fake:{request.request_id}",
            actual_model=self.model_name,
            files=[
                GeneratedFileFact(
                    storage_key=f"fake/{request_key}/image-1.png",
                    sha256="0" * 64,
                    size_bytes=1024,
                    mime_type="image/png",
                    width=request.width,
                    height=request.height,
                )
            ],
            usage=ModelUsage(output_units={"images": 1}, cost=Decimal("0")),
        )


class DeterministicFakeVideoProvider:
    provider_name = "deterministic-fake"
    model_name = "fake-video-v1"

    def __init__(self, scenario: FakeVideoScenario = FakeVideoScenario.SUCCESS) -> None:
        self._scenario = scenario
        self._poll_counts: dict[str, int] = {}
        self.submit_calls = 0
        self.cancel_calls = 0

    async def submit(
        self,
        request: VideoModelRequest,
        *,
        organization_id: UUID | None = None,
    ) -> VideoProviderResult:
        self.submit_calls += 1
        if self._scenario == FakeVideoScenario.SUBMISSION_UNKNOWN:
            raise ModelGatewayError(GatewayErrorCode.SUBMISSION_UNKNOWN, retryable=False)
        task_id = f"fake-task:{_fake_key(request.request_id)}"
        self._poll_counts[task_id] = 0
        return self._result(
            request_id=request.request_id,
            task_id=task_id,
            status=VideoOperationStatus.SUBMITTED,
        )

    async def poll(self, request: VideoPollRequest) -> VideoProviderResult:
        if request.provider_task_id not in self._poll_counts:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
        self._poll_counts[request.provider_task_id] += 1
        if self._scenario == FakeVideoScenario.FAILED:
            status = VideoOperationStatus.FAILED
        elif self._poll_counts[request.provider_task_id] == 1:
            status = VideoOperationStatus.POLLING
        else:
            status = VideoOperationStatus.SUCCEEDED
        return self._result(
            request_id=request.request_id,
            task_id=request.provider_task_id,
            status=status,
        )

    async def cancel(self, request: VideoPollRequest) -> VideoProviderResult:
        if request.provider_task_id not in self._poll_counts:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
        self.cancel_calls += 1
        return self._result(
            request_id=request.request_id,
            task_id=request.provider_task_id,
            status=VideoOperationStatus.CANCELLED,
        )

    def _result(
        self,
        *,
        request_id: str,
        task_id: str,
        status: VideoOperationStatus,
    ) -> VideoProviderResult:
        files = []
        usage = ModelUsage(cost=Decimal("0"))
        if status == VideoOperationStatus.SUCCEEDED:
            files = [
                GeneratedFileFact(
                    storage_key=f"fake/{task_id.replace(':', '-')}/video.mp4",
                    sha256="1" * 64,
                    size_bytes=2048,
                    mime_type="video/mp4",
                    duration_seconds=8,
                )
            ]
            usage = ModelUsage(output_units={"video_seconds": 8}, cost=Decimal("0"))
        return VideoProviderResult(
            status=status,
            provider_request_id=f"fake:{request_id}",
            provider_task_id=task_id,
            actual_model=self.model_name,
            files=files,
            usage=usage,
        )


def _fake_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
