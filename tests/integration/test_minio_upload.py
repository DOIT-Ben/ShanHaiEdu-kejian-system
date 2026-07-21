from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from minio import Minio

from apps.api.settings import Settings
from apps.api.uploads.storage import ObjectStorageError, build_object_storage


@pytest.mark.integration
def test_real_minio_presign_put_stat_copy_and_bounded_download(tmp_path: Path) -> None:
    settings = Settings(_env_file=None)
    if not (
        settings.object_storage_endpoint
        and settings.object_storage_access_key
        and settings.object_storage_secret_key
    ):
        pytest.skip("object storage credentials are only configured for explicit integration runs")
    storage = build_object_storage(settings)
    assert storage is not None
    content = b"stage0 object storage smoke"
    sha256 = hashlib.sha256(content).hexdigest()
    key = f"integration/{uuid4().hex}/lesson.pdf"
    immutable_key = f"integration/{uuid4().hex}/immutable.pdf"
    url = storage.create_presigned_put(
        bucket=settings.object_storage_bucket,
        key=key,
        expires=timedelta(minutes=5),
    )
    cleanup_client = Minio(
        settings.object_storage_endpoint,
        access_key=settings.object_storage_access_key.get_secret_value(),
        secret_key=settings.object_storage_secret_key.get_secret_value(),
        secure=settings.object_storage_secure,
    )
    try:
        response = httpx.put(
            url,
            content=content,
            headers={"Content-Type": "application/pdf"},
            timeout=10,
        )
        assert response.status_code == 200, response.text
        metadata = storage.stat(bucket=settings.object_storage_bucket, key=key)
        assert metadata.key == key
        assert metadata.etag == response.headers["ETag"].strip('"')
        assert metadata.size_bytes == len(content)
        assert metadata.media_type == "application/pdf"
        assert metadata.sha256 == sha256
        copied = storage.copy(
            source_bucket=settings.object_storage_bucket,
            source_key=key,
            destination_bucket=settings.object_storage_bucket,
            destination_key=immutable_key,
        )
        assert copied.key == immutable_key
        assert copied.sha256 == sha256
        download_path = tmp_path / "downloaded.pdf"
        downloaded = storage.download_to_path(
            bucket=settings.object_storage_bucket,
            key=immutable_key,
            destination=download_path,
            max_bytes=len(content),
        )
        assert downloaded.size_bytes == len(content)
        assert downloaded.media_type == "application/pdf"
        assert downloaded.sha256 == sha256
        assert download_path.read_bytes() == content
        rejected_path = tmp_path / "rejected.pdf"
        with pytest.raises(ObjectStorageError):
            storage.download_to_path(
                bucket=settings.object_storage_bucket,
                key=immutable_key,
                destination=rejected_path,
                max_bytes=len(content) - 1,
            )
        assert not rejected_path.exists()
        storage.delete(bucket=settings.object_storage_bucket, key=key)
        with pytest.raises(ObjectStorageError):
            storage.stat(bucket=settings.object_storage_bucket, key=key)
    finally:
        cleanup_client.remove_object(settings.object_storage_bucket, key)
        cleanup_client.remove_object(settings.object_storage_bucket, immutable_key)
