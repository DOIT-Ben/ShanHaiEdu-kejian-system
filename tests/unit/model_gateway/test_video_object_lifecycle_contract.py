from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

import pytest

from apps.api.model_gateway.contracts import (
    MediaReference,
    ModelCapability,
    VideoModelRequest,
    VideoPollRequest,
    VideoResultScope,
)
from apps.api.model_gateway.object_storage_video_store import (
    ObjectStorageVideoResultStore,
    build_video_final_key,
    build_video_staging_key,
)
from tests.fakes.object_storage import FakeObjectStorage


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
        "assets/video-results/"
        f"{ORG_ID}/{PROJECT_ID}/{LESSON_ID}/{JOB_ID}/"
        f"{'a' * 64}.mp4"
    )
    assert TASK_ID not in staging
    assert TASK_ID not in final
    assert hashlib.sha256(TASK_ID.encode()).hexdigest()[:32] in staging


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


def test_gc_never_deletes_a_bound_final_object() -> None:
    from apps.api.model_gateway.object_storage_video_store import cleanup_video_objects

    storage = FakeObjectStorage()
    storage.put_bytes(
        bucket="shanhaiedu",
        key=build_video_final_key(scope(), sha256="b" * 64),
        payload=b"bound-final",
        media_type="video/mp4",
    )

    result = cleanup_video_objects(
        storage,
        bucket="shanhaiedu",
        now=2_000_000,
        dry_run=False,
        bound_final_keys={build_video_final_key(scope(), sha256="b" * 64)},
    )

    assert result.deleted_count == 0
    assert storage.object_count == 1
