from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    MediaReference,
    ModelCapability,
    ModelGatewayError,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
)
from apps.api.model_gateway.newapi_video import (
    NewApiVideoConfig,
    NewApiVideoProvider,
    StoredVideoFile,
)

TASK_ID = "018f0000-0000-7000-8000-000000000001"


class RecordingVideoStore:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes, str]] = []

    def persist(
        self,
        *,
        key: str,
        source: Path,
        media_type: str,
    ) -> StoredVideoFile:
        payload = source.read_bytes()
        self.uploads.append((key, payload, media_type))
        return StoredVideoFile(
            storage_key=key,
            size_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            mime_type=media_type,
        )


def video_request(*, references: list[MediaReference] | None = None) -> VideoModelRequest:
    return VideoModelRequest(
        capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
        request_id="req-video-provider-test",
        prompt="A simple paper boat moves across a calm blue pond.",
        duration_seconds=6,
        references=references or [],
    )


def provider(
    handler,
    store: RecordingVideoStore,
    *,
    max_download_bytes: int = 10_000_000,
) -> NewApiVideoProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return NewApiVideoProvider(
        NewApiVideoConfig(
            provider_name="newapi",
            base_url="https://gateway.test/v1",
            model="video-grok",
            api_key=SecretStr("test-only-key"),
            timeout_seconds=5,
            max_download_bytes=max_download_bytes,
        ),
        store=store,
        client=client,
    )


async def test_submit_maps_gateway_task_and_sends_generated_idempotency_key() -> None:
    store = RecordingVideoStore()

    def handler(http_request: httpx.Request) -> httpx.Response:
        assert http_request.url == "https://gateway.test/v1/videos"
        assert http_request.headers["Authorization"] == "Bearer test-only-key"
        assert http_request.headers["Idempotency-Key"] == (
            "video-smoke-" + hashlib.sha256(b"req-video-provider-test").hexdigest()
        )
        assert json.loads(http_request.content) == {
            "model": "video-grok",
            "prompt": "A simple paper boat moves across a calm blue pond.",
            "duration": 6,
        }
        return httpx.Response(
            200,
            headers={"X-Request-ID": "gateway-submit-1"},
            json={
                "id": TASK_ID,
                "model": "video-grok",
                "status": "queued",
                "createdAt": "2026-07-21T00:00:00Z",
            },
        )

    result = await provider(handler, store).submit(video_request())

    assert result.status == VideoOperationStatus.SUBMITTED
    assert result.provider_task_id == TASK_ID
    assert result.provider_request_id == "gateway-submit-1"
    assert result.files == []
    assert store.uploads == []


async def test_completed_poll_downloads_mp4_and_persists_a_hashed_file() -> None:
    store = RecordingVideoStore()
    video_bytes = b"real-mp4-bytes-for-adapter-test"

    def handler(http_request: httpx.Request) -> httpx.Response:
        if http_request.url == f"https://gateway.test/v1/videos/{TASK_ID}":
            return httpx.Response(
                200,
                headers={"X-Request-ID": "gateway-poll-1"},
                json={
                    "id": TASK_ID,
                    "model": "video-grok",
                    "status": "completed",
                    "hasOutput": True,
                    "createdAt": "2026-07-21T00:00:00Z",
                    "updatedAt": "2026-07-21T00:00:03Z",
                },
            )
        assert http_request.url == f"https://gateway.test/v1/videos/{TASK_ID}/content"
        return httpx.Response(
            200,
            headers={"Content-Type": "video/mp4", "X-Request-ID": "gateway-content-1"},
            content=video_bytes,
        )

    result = await provider(handler, store).poll(
        VideoPollRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id="req-video-poll-test",
            provider_task_id=TASK_ID,
        )
    )

    expected_sha = hashlib.sha256(video_bytes).hexdigest()
    assert result.status == VideoOperationStatus.SUCCEEDED
    assert result.provider_task_id == TASK_ID
    assert result.provider_request_id == "gateway-content-1"
    assert result.files[0].storage_key == f"model-smoke/video/{TASK_ID}.mp4"
    assert result.files[0].sha256 == expected_sha
    assert result.files[0].size_bytes == len(video_bytes)
    assert result.files[0].mime_type == "video/mp4"
    assert store.uploads == [(f"model-smoke/video/{TASK_ID}.mp4", video_bytes, "video/mp4")]


async def test_submit_fails_closed_when_private_asset_references_cannot_be_resolved() -> None:
    store = RecordingVideoStore()

    def handler(_http_request: httpx.Request) -> httpx.Response:
        raise AssertionError("the provider must not receive an invented reference URL")

    reference = MediaReference(
        file_version_id=UUID("018f0000-0000-7000-8000-000000000002"),
        mime_type="image/png",
    )
    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler, store).submit(video_request(references=[reference]))

    assert captured.value.code == GatewayErrorCode.ROUTE_UNAVAILABLE
    assert captured.value.retryable is False


async def test_submit_conflict_becomes_submission_unknown_without_a_second_request() -> None:
    store = RecordingVideoStore()

    def handler(_http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            headers={"X-Request-ID": "gateway-conflict-1"},
            json={"error": {"code": "conflict", "message": "hidden", "type": "conflict"}},
        )

    result = await provider(handler, store).submit(video_request())

    assert result.status == VideoOperationStatus.SUBMISSION_UNKNOWN
    assert result.provider_task_id is None
    assert result.provider_request_id == "gateway-conflict-1"


async def test_completed_poll_rejects_non_mp4_content_without_persisting_it() -> None:
    store = RecordingVideoStore()

    def handler(http_request: httpx.Request) -> httpx.Response:
        if http_request.url == f"https://gateway.test/v1/videos/{TASK_ID}":
            return httpx.Response(
                200,
                json={
                    "id": TASK_ID,
                    "model": "video-grok",
                    "status": "completed",
                    "createdAt": "2026-07-21T00:00:00Z",
                },
            )
        return httpx.Response(200, headers={"Content-Type": "text/html"}, content=b"not-a-video")

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler, store).poll(
            VideoPollRequest(
                capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
                request_id="req-video-poll-invalid-content",
                provider_task_id=TASK_ID,
            )
        )

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE
    assert store.uploads == []


async def test_completed_poll_rejects_a_stream_that_exceeds_the_download_limit() -> None:
    store = RecordingVideoStore()

    def handler(http_request: httpx.Request) -> httpx.Response:
        if http_request.url == f"https://gateway.test/v1/videos/{TASK_ID}":
            return httpx.Response(
                200,
                json={
                    "id": TASK_ID,
                    "model": "video-grok",
                    "status": "completed",
                    "createdAt": "2026-07-21T00:00:00Z",
                },
            )
        return httpx.Response(
            200,
            headers={"Content-Type": "video/mp4"},
            content=b"video-payload-that-exceeds-the-limit",
        )

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler, store, max_download_bytes=8).poll(
            VideoPollRequest(
                capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
                request_id="req-video-poll-too-large",
                provider_task_id=TASK_ID,
            )
        )

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE
    assert store.uploads == []
