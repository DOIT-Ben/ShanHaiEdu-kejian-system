from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta

from apps.api.uploads.storage import ObjectMetadata, ObjectStorageError


@dataclass(frozen=True, slots=True)
class PresignedPut:
    bucket: str
    key: str
    expires: timedelta


class FakeObjectStorage:
    def __init__(self) -> None:
        self.last_presigned: PresignedPut | None = None
        self._objects: dict[tuple[str, str], ObjectMetadata] = {}

    def create_presigned_put(
        self,
        *,
        bucket: str,
        key: str,
        expires: timedelta,
    ) -> str:
        self.last_presigned = PresignedPut(bucket=bucket, key=key, expires=expires)
        return f"https://object-storage.test/{bucket}/{key}?signature=fake"

    def stat(self, *, bucket: str, key: str) -> ObjectMetadata:
        try:
            return self._objects[(bucket, key)]
        except KeyError as exc:
            raise ObjectStorageError("fake object not found") from exc

    def put(self, metadata: ObjectMetadata) -> None:
        self._objects[(metadata.bucket, metadata.key)] = metadata

    def put_at(self, *, bucket: str, key: str, metadata: ObjectMetadata) -> None:
        self._objects[(bucket, key)] = metadata

    def copy(
        self,
        *,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
    ) -> ObjectMetadata:
        source = self.stat(bucket=source_bucket, key=source_key)
        copied = replace(source, bucket=destination_bucket, key=destination_key)
        self.put(copied)
        return copied

    def delete(self, *, bucket: str, key: str) -> None:
        self._objects.pop((bucket, key), None)
