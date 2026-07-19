from __future__ import annotations

import hashlib

import pytest

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ImageModelRequest,
    ModelCapability,
    ModelGatewayError,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
)
from apps.api.model_gateway.fake import (
    DeterministicFakeImageProvider,
    DeterministicFakeVideoProvider,
    FakeScenario,
    FakeVideoScenario,
)
from apps.api.model_gateway.gateway import ModelGateway


def image_request() -> ImageModelRequest:
    return ImageModelRequest(
        capability=ModelCapability.IMAGE_GENERATE_EDUCATION_16X9,
        request_id="req-fake-image",
        prompt="A clean classroom diagram.",
        width=1280,
        height=720,
    )


def video_request() -> VideoModelRequest:
    return VideoModelRequest(
        capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
        request_id="req-fake-video",
        prompt="Animate the classroom diagram.",
        duration_seconds=8,
        references=[],
    )


async def test_image_fake_returns_file_facts_without_writing_media() -> None:
    gateway = ModelGateway(
        {},
        image_routes={
            ModelCapability.IMAGE_GENERATE_EDUCATION_16X9: DeterministicFakeImageProvider()
        },
    )

    result = await gateway.generate_image(image_request())

    assert result.kind == "image"
    request_key = hashlib.sha256(b"req-fake-image").hexdigest()[:24]
    assert result.files[0].storage_key == f"fake/{request_key}/image-1.png"
    assert result.files[0].sha256 == "0" * 64
    assert result.usage.output_units == {"images": 1}


@pytest.mark.parametrize(
    ("scenario", "code", "retryable"),
    [
        (FakeScenario.RATE_LIMITED, GatewayErrorCode.PROVIDER_RATE_LIMITED, True),
        (FakeScenario.TIMEOUT, GatewayErrorCode.TIMEOUT, True),
        (FakeScenario.UNAVAILABLE, GatewayErrorCode.PROVIDER_UNAVAILABLE, True),
        (FakeScenario.REJECTED, GatewayErrorCode.REJECTED, False),
        (FakeScenario.CANCELLED, GatewayErrorCode.CANCELLED, False),
    ],
)
async def test_image_fake_uses_shared_error_contract(
    scenario: FakeScenario,
    code: GatewayErrorCode,
    retryable: bool,
) -> None:
    gateway = ModelGateway(
        {},
        image_routes={
            ModelCapability.IMAGE_GENERATE_EDUCATION_16X9: DeterministicFakeImageProvider(scenario)
        },
    )

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.generate_image(image_request())

    assert captured.value.code == code
    assert captured.value.retryable is retryable


async def test_video_fake_submits_polls_and_returns_recoverable_task_id() -> None:
    provider = DeterministicFakeVideoProvider()
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
    )

    submitted = await gateway.submit_video(video_request())
    polling = await gateway.poll_video(
        VideoPollRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id="req-fake-video-poll-1",
            provider_task_id=submitted.provider_task_id,
        )
    )
    succeeded = await gateway.poll_video(
        VideoPollRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id="req-fake-video-poll-2",
            provider_task_id=submitted.provider_task_id,
        )
    )

    assert submitted.status == VideoOperationStatus.SUBMITTED
    assert polling.status == VideoOperationStatus.POLLING
    assert succeeded.status == VideoOperationStatus.SUCCEEDED
    assert succeeded.provider_task_id == submitted.provider_task_id
    assert succeeded.files[0].mime_type == "video/mp4"
    assert provider.submit_calls == 1


async def test_submission_unknown_is_not_retryable_and_never_auto_resubmitted() -> None:
    provider = DeterministicFakeVideoProvider(FakeVideoScenario.SUBMISSION_UNKNOWN)
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
    )

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.submit_video(video_request())

    assert captured.value.code == GatewayErrorCode.SUBMISSION_UNKNOWN
    assert captured.value.retryable is False
    assert provider.submit_calls == 1


async def test_video_cancel_uses_existing_task_instead_of_submitting_again() -> None:
    provider = DeterministicFakeVideoProvider()
    gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
    )
    submitted = await gateway.submit_video(video_request())

    cancelled = await gateway.cancel_video(
        VideoPollRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id="req-fake-video-cancel",
            provider_task_id=submitted.provider_task_id,
        )
    )

    assert cancelled.status == VideoOperationStatus.CANCELLED
    assert provider.submit_calls == 1
    assert provider.cancel_calls == 1
