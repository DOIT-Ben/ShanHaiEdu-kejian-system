from __future__ import annotations

import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import ClassVar, cast

import pytest
from minio import Minio

from apps.api.uploads.storage import MinioObjectStorage
from tests.fakes.object_storage import FakeObjectStorage


def test_minio_stat_preserves_last_modified_for_gc_recheck() -> None:
    modified = datetime(2026, 7, 1, 2, 3, 4, tzinfo=UTC)

    class Response:
        headers: ClassVar[dict[str, str]] = {
            "etag": '"etag"',
            "content-length": "5",
            "content-type": "video/mp4",
            "last-modified": format_datetime(modified, usegmt=True),
        }

        def __init__(self) -> None:
            self._read = False

        def read(self, _size: int) -> bytes:
            if self._read:
                return b""
            self._read = True
            return b"video"

        def close(self) -> None:
            return None

        def release_conn(self) -> None:
            return None

    class Client:
        def get_object(self, bucket: str, key: str) -> Response:
            assert bucket == "shanhaiedu"
            assert key.endswith(".mp4")
            return Response()

    storage = object.__new__(MinioObjectStorage)
    storage._client = cast(Minio, Client())  # pyright: ignore[reportPrivateUsage]

    metadata = storage.stat(bucket="shanhaiedu", key="staging/video-results/test.mp4")

    assert metadata.last_modified == modified


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], (False, 100)),
        (["--execute", "--limit", "7"], (True, 7)),
    ],
)
def test_video_object_cleanup_cli_is_dry_run_by_default(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    expected: tuple[bool, int],
) -> None:
    from apps.api import cli_main

    calls: list[tuple[bool, int]] = []

    def run(*, execute: bool, limit: int) -> int:
        calls.append((execute, limit))
        return 0

    monkeypatch.setattr(cli_main, "run_video_object_cleanup", run)
    monkeypatch.setattr(sys, "argv", ["shanhaiedu", "video-object-cleanup", *arguments])

    assert cli_main.main() == 0
    assert calls == [expected]


def test_object_storage_bounded_listing_returns_oldest_objects() -> None:
    storage = FakeObjectStorage()
    now = datetime(2026, 7, 31, 6, 0, tzinfo=UTC)
    for index in range(100):
        key = f"staging/video-results/{index:03d}-young.mp4"
        metadata = storage.put_bytes(
            bucket="shanhaiedu",
            key=key,
            payload=f"young-{index}".encode(),
            media_type="video/mp4",
        )
        storage.put_at(
            bucket="shanhaiedu",
            key=key,
            metadata=replace(metadata, last_modified=now - timedelta(minutes=1)),
        )
    old_key = "staging/video-results/zzz-old.mp4"
    old_metadata = storage.put_bytes(
        bucket="shanhaiedu",
        key=old_key,
        payload=b"old",
        media_type="video/mp4",
    )
    storage.put_at(
        bucket="shanhaiedu",
        key=old_key,
        metadata=replace(old_metadata, last_modified=now - timedelta(days=2)),
    )

    objects = storage.list_objects(
        bucket="shanhaiedu",
        prefix="staging/video-results/",
        limit=100,
    )

    assert len(objects) == 100
    assert objects[0].key == old_key
