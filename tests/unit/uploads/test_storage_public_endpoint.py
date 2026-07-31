from __future__ import annotations

from datetime import timedelta

from apps.api.uploads.storage import MinioObjectStorage


class RecordingMinio:
    instances: list["RecordingMinio"] = []

    def __init__(self, endpoint: str, **_: object) -> None:
        self.endpoint = endpoint
        self.instances.append(self)

    def bucket_exists(self, _bucket: str) -> bool:
        return True

    def presigned_put_object(self, bucket: str, key: str, *, expires: timedelta) -> str:
        assert expires == timedelta(minutes=5)
        return f"https://{self.endpoint}/{bucket}/{key}"


def test_presigned_upload_uses_public_endpoint_without_routing_server_operations_through_it(
    monkeypatch,
) -> None:
    RecordingMinio.instances = []
    monkeypatch.setattr("apps.api.uploads.storage.Minio", RecordingMinio)

    storage = MinioObjectStorage(
        endpoint="minio:9000",
        public_endpoint="203.0.113.10",
        access_key="access-key",
        secret_key="secret-key",
        secure=False,
        public_secure=True,
        create_bucket_if_missing=False,
        timeout_seconds=2,
    )

    url = storage.create_presigned_put(
        bucket="shanhaiedu-production",
        key="materials/lesson.pdf",
        expires=timedelta(minutes=5),
    )

    assert [client.endpoint for client in RecordingMinio.instances] == [
        "minio:9000",
        "203.0.113.10",
    ]
    assert url == (
        "https://203.0.113.10/shanhaiedu-production/materials/lesson.pdf"
    )
