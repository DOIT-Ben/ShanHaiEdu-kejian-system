from __future__ import annotations

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from apps.api.model_gateway.contracts import (
    GeneratedFileFact,
    ImageModelRequest,
    ImageProviderResult,
    MediaReference,
    ModelCapability,
    ModelRequest,
    ModelResult,
    ModelUsage,
    TextModelRequest,
    VideoGatewayResult,
    VideoModelRequest,
    VideoOperationStatus,
    VideoProviderResult,
)


def test_model_request_union_uses_explicit_media_discriminator() -> None:
    adapter = TypeAdapter(ModelRequest)

    text = adapter.validate_python(
        {
            "kind": "text",
            "capability": "text.smoke",
            "request_id": "req-text",
            "prompt": "hello",
        }
    )
    image = adapter.validate_python(
        {
            "kind": "image",
            "capability": "image.generate.education_16x9",
            "request_id": "req-image",
            "prompt": "classroom illustration",
            "width": 1280,
            "height": 720,
        }
    )
    video = adapter.validate_python(
        {
            "kind": "video",
            "capability": "video.image_to_video.6s_30s",
            "request_id": "req-video",
            "prompt": "animate the scene",
            "duration_seconds": 8,
            "references": [
                {
                    "kind": "file_asset_version",
                    "file_version_id": "01980000-0000-7000-8000-000000000001",
                    "mime_type": "image/png",
                }
            ],
        }
    )

    assert isinstance(text, TextModelRequest)
    assert isinstance(image, ImageModelRequest)
    assert isinstance(video, VideoModelRequest)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "kind": "image",
            "capability": "text.smoke",
            "request_id": "req-wrong-media",
            "prompt": "wrong route",
            "width": 1280,
            "height": 720,
        },
        {
            "kind": "video",
            "capability": "video.image_to_video.6s_30s",
            "request_id": "req-extra-field",
            "prompt": "animate",
            "duration_seconds": 8,
            "references": [],
            "provider_private_option": "must-not-cross-platform-boundary",
        },
    ],
)
def test_model_requests_fail_closed_for_wrong_media_or_private_fields(
    payload: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(ModelRequest).validate_python(payload)


def test_model_result_union_is_discriminated_and_forbids_provider_payloads() -> None:
    payload = {
        "kind": "image",
        "request_id": "req-image-result",
        "route": {
            "capability": "image.generate.education_16x9",
            "provider": "deterministic-fake",
            "model": "fake-image-v1",
            "reason": "configured_primary",
        },
        "provider_request_id": "fake:req-image-result",
        "actual_model": "fake-image-v1",
        "files": [
            {
                "kind": "generated_file",
                "storage_key": "fake/req-image-result/image-1.png",
                "sha256": "0" * 64,
                "size_bytes": 1024,
                "mime_type": "image/png",
                "width": 1280,
                "height": 720,
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "output_units": {"images": 1},
        },
        "latency_ms": 1,
        "raw_provider_response": {"secret": "must fail"},
    }

    with pytest.raises(ValidationError):
        TypeAdapter(ModelResult).validate_python(payload)


def test_video_status_requires_recoverable_task_id_and_terminal_file_facts() -> None:
    usage = ModelUsage(output_units={"video_seconds": 8})
    file = GeneratedFileFact(
        storage_key="fake/req-video/video.mp4",
        sha256="1" * 64,
        size_bytes=2048,
        mime_type="video/mp4",
        duration_seconds=8,
    )

    submitted = VideoProviderResult(
        status=VideoOperationStatus.SUBMITTED,
        provider_request_id="provider-request-1",
        provider_task_id="provider-task-1",
        actual_model="fake-video-v1",
        files=[],
        usage=ModelUsage(),
    )
    succeeded = VideoProviderResult(
        status=VideoOperationStatus.SUCCEEDED,
        provider_request_id="provider-request-2",
        provider_task_id="provider-task-1",
        actual_model="fake-video-v1",
        files=[file],
        usage=usage,
    )

    assert submitted.provider_task_id == succeeded.provider_task_id
    with pytest.raises(ValidationError):
        VideoProviderResult(
            status=VideoOperationStatus.SUBMITTED,
            provider_request_id="provider-request-missing-task",
            provider_task_id=None,
            actual_model="fake-video-v1",
            files=[],
            usage=ModelUsage(),
        )
    with pytest.raises(ValidationError):
        VideoProviderResult(
            status=VideoOperationStatus.SUCCEEDED,
            provider_request_id="provider-request-missing-file",
            provider_task_id="provider-task-1",
            actual_model="fake-video-v1",
            files=[],
            usage=usage,
        )


def test_platform_media_reference_contains_no_provider_transport_fields() -> None:
    reference = MediaReference(
        file_version_id="01980000-0000-7000-8000-000000000001",
        mime_type="image/png",
    )

    assert reference.model_dump(mode="json") == {
        "kind": "file_asset_version",
        "file_version_id": "01980000-0000-7000-8000-000000000001",
        "mime_type": "image/png",
    }
    assert ModelCapability.IMAGE_GENERATE_EDUCATION_16X9.value.startswith("image.")
    assert ImageProviderResult.model_config["extra"] == "forbid"


@pytest.mark.parametrize(
    "storage_key",
    [
        "https://provider.test/private-result.png",
        "/absolute/result.png",
        "generated/../private/result.png",
        "generated\\private\\result.png",
    ],
)
def test_generated_file_facts_reject_provider_urls_and_unsafe_paths(storage_key: str) -> None:
    with pytest.raises(ValidationError):
        GeneratedFileFact(
            storage_key=storage_key,
            sha256="2" * 64,
            size_bytes=1,
            mime_type="image/png",
        )


def test_usage_units_are_nonnegative_and_provider_neutral() -> None:
    with pytest.raises(ValidationError):
        ModelUsage(output_units={"images": -1})


def test_media_results_enforce_file_type_and_recoverable_video_state() -> None:
    video_file = GeneratedFileFact(
        storage_key="generated/video.mp4",
        sha256="3" * 64,
        size_bytes=1,
        mime_type="video/mp4",
        duration_seconds=8,
    )
    image_file = GeneratedFileFact(
        storage_key="generated/image.png",
        sha256="4" * 64,
        size_bytes=1,
        mime_type="image/png",
        width=1280,
        height=720,
    )

    with pytest.raises(ValidationError):
        ImageProviderResult(
            provider_request_id="provider-request-wrong-media",
            actual_model="fake-image-v1",
            files=[video_file],
            usage=ModelUsage(),
        )
    with pytest.raises(ValidationError):
        VideoProviderResult(
            status=VideoOperationStatus.SUCCEEDED,
            provider_request_id="provider-request-wrong-media",
            provider_task_id="provider-task-1",
            actual_model="fake-video-v1",
            files=[image_file],
            usage=ModelUsage(),
        )
    with pytest.raises(ValidationError):
        VideoGatewayResult(
            request_id="req-invalid-submitted-result",
            status=VideoOperationStatus.SUBMITTED,
            route={
                "capability": "video.image_to_video.6s_30s",
                "provider": "provider-test",
                "model": "provider-model",
                "reason": "configured_primary",
            },
            provider_request_id="provider-request-1",
            provider_task_id=None,
            actual_model="provider-model",
            files=[],
            usage=ModelUsage(),
            latency_ms=1,
        )
