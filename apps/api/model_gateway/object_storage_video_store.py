from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path

from apps.api.model_gateway.contracts import VideoResultScope
from apps.api.model_gateway.video_store import StoredVideoFile
from apps.api.uploads.storage import (
    ObjectMetadata,
    ObjectNotFoundError,
    ObjectStorage,
    ObjectStorageError,
)

_STAGING_PREFIX = "staging/video-results"
_FINAL_PREFIX = "assets/video-results"


@dataclass(frozen=True, slots=True)
class VideoCleanupResult:
    scanned_count: int
    candidate_count: int
    deleted_count: int


class ObjectStorageVideoResultStore:
    def __init__(
        self,
        storage: ObjectStorage,
        *,
        bucket: str,
        max_bytes: int,
    ) -> None:
        self._storage = storage
        self._bucket = bucket
        self._max_bytes = max_bytes

    def persist(
        self,
        *,
        key: str,
        source: Path,
        media_type: str,
    ) -> StoredVideoFile:
        if media_type != "video/mp4" or not source.is_file():
            raise OSError("video result source is invalid")
        size = source.stat().st_size
        if size <= 0 or size > self._max_bytes:
            raise OSError("video result size is invalid")
        payload = source.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        try:
            metadata = self._storage.put_bytes(
                bucket=self._bucket,
                key=key,
                payload=payload,
                media_type=media_type,
            )
        except ObjectStorageError as exc:
            raise OSError("video result storage failed") from exc
        if (
            metadata.media_type != media_type
            or metadata.size_bytes != size
            or metadata.sha256 != digest
        ):
            try:
                self._storage.delete(bucket=self._bucket, key=key)
            except ObjectStorageError:
                pass
            raise OSError("stored video result facts do not match")
        return StoredVideoFile(
            storage_key=key,
            sha256=digest,
            size_bytes=size,
            mime_type=media_type,
        )

    def stage(
        self,
        *,
        source: Path,
        media_type: str,
        scope: VideoResultScope,
        provider_name: str,
        provider_task_id: str,
    ) -> StoredVideoFile:
        key = build_video_staging_key(
            scope,
            provider_name=provider_name,
            provider_task_id=provider_task_id,
        )
        return self.persist(key=key, source=source, media_type=media_type)

    def promote(
        self,
        *,
        staged: StoredVideoFile,
        scope: VideoResultScope,
    ) -> StoredVideoFile:
        expected_prefix = _scope_prefix(_STAGING_PREFIX, scope)
        if not staged.storage_key.startswith(f"{expected_prefix}/"):
            raise OSError("staged video result ownership does not match")
        final_key = build_video_final_key(scope, sha256=staged.sha256)
        try:
            existing = self._storage.stat(bucket=self._bucket, key=final_key)
        except ObjectNotFoundError:
            try:
                existing = self._storage.copy(
                    source_bucket=self._bucket,
                    source_key=staged.storage_key,
                    destination_bucket=self._bucket,
                    destination_key=final_key,
                )
            except ObjectStorageError as exc:
                try:
                    existing = self._storage.stat(bucket=self._bucket, key=final_key)
                except ObjectStorageError:
                    raise OSError("video result promotion failed") from exc
        except ObjectStorageError as exc:
            raise OSError("video result promotion failed") from exc
        _require_object_facts(existing, staged, final_key)
        return StoredVideoFile(
            storage_key=final_key,
            sha256=staged.sha256,
            size_bytes=staged.size_bytes,
            mime_type=staged.mime_type,
        )


def build_video_staging_key(
    scope: VideoResultScope,
    *,
    provider_name: str,
    provider_task_id: str,
) -> str:
    if not provider_name.strip() or not provider_task_id.strip():
        raise ValueError("video staging provider identity is required")
    task_hash = hashlib.sha256(f"{provider_name}\0{provider_task_id}".encode()).hexdigest()[:32]
    return f"{_scope_prefix(_STAGING_PREFIX, scope)}/{task_hash}.mp4"


def build_video_final_key(scope: VideoResultScope, *, sha256: str) -> str:
    if not _is_sha256(sha256):
        raise ValueError("video final key requires a SHA-256 digest")
    return f"{_scope_prefix(_FINAL_PREFIX, scope)}/{sha256}.mp4"


def cleanup_video_objects(
    storage: ObjectStorage,
    *,
    bucket: str,
    now: float,
    bound_final_keys: set[str],
    dry_run: bool = True,
    eligible_staging_keys: set[str] | None = None,
    eligible_unbound_final_keys: set[str] | None = None,
    staging_ttl_seconds: int = 86_400,
    unbound_final_ttl_seconds: int = 604_800,
    limit: int = 100,
) -> VideoCleanupResult:
    if not 1 <= limit <= 100 or staging_ttl_seconds <= 0 or unbound_final_ttl_seconds <= 0:
        raise ValueError("video cleanup limits are outside supported bounds")
    staging_eligible = eligible_staging_keys or set()
    final_eligible = eligible_unbound_final_keys or set()
    objects = sorted(
        [
            *storage.list_objects(bucket=bucket, prefix=f"{_STAGING_PREFIX}/", limit=limit),
            *storage.list_objects(bucket=bucket, prefix=f"{_FINAL_PREFIX}/", limit=limit),
        ],
        key=_cleanup_age_order,
    )[:limit]
    candidates: list[ObjectMetadata] = []
    for metadata in objects:
        if metadata.key in bound_final_keys:
            continue
        if metadata.key.startswith(f"{_STAGING_PREFIX}/"):
            eligible = metadata.key in staging_eligible
            ttl = staging_ttl_seconds
        elif metadata.key.startswith(f"{_FINAL_PREFIX}/"):
            eligible = metadata.key in final_eligible
            ttl = unbound_final_ttl_seconds
        else:
            continue
        if eligible and _older_than(metadata, now=now, ttl_seconds=ttl):
            candidates.append(metadata)
    deleted_count = 0
    if not dry_run:
        for metadata in candidates:
            current = storage.stat(bucket=bucket, key=metadata.key)
            if current.key != metadata.key or not _older_than(
                current,
                now=now,
                ttl_seconds=(
                    staging_ttl_seconds
                    if metadata.key.startswith(f"{_STAGING_PREFIX}/")
                    else unbound_final_ttl_seconds
                ),
            ):
                continue
            if _delete_confirmed(storage, bucket=bucket, key=metadata.key):
                deleted_count += 1
    return VideoCleanupResult(
        scanned_count=len(objects),
        candidate_count=len(candidates),
        deleted_count=deleted_count,
    )


def _scope_prefix(prefix: str, scope: VideoResultScope) -> str:
    return (
        f"{prefix}/{scope.organization_id}/{scope.project_id}/"
        f"{scope.lesson_unit_id}/{scope.generation_job_id}"
    )


def _require_object_facts(
    metadata: ObjectMetadata,
    staged: StoredVideoFile,
    final_key: str,
) -> None:
    if (
        metadata.key != final_key
        or metadata.media_type != staged.mime_type
        or metadata.size_bytes != staged.size_bytes
        or metadata.sha256 != staged.sha256
    ):
        raise OSError("promotion destination facts do not match")


def _older_than(metadata: ObjectMetadata, *, now: float, ttl_seconds: int) -> bool:
    modified = metadata.last_modified
    if modified is None:
        return False
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=UTC)
    return modified.timestamp() <= now - ttl_seconds


def _delete_confirmed(storage: ObjectStorage, *, bucket: str, key: str) -> bool:
    storage.delete(bucket=bucket, key=key)
    try:
        storage.stat(bucket=bucket, key=key)
    except ObjectNotFoundError:
        return True
    except ObjectStorageError:
        return False
    return False


def _cleanup_age_order(metadata: ObjectMetadata) -> tuple[float, str]:
    modified = metadata.last_modified
    if modified is None:
        return (float("inf"), metadata.key)
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=UTC)
    return (modified.timestamp(), metadata.key)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
