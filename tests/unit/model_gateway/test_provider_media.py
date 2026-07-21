from __future__ import annotations

import hashlib
import os
from pathlib import Path
from time import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest

from apps.api.assets.provider_media import ProviderMediaAssetVersion
from apps.api.model_gateway.contracts import MediaReference
from apps.api.model_gateway.provider_media import (
    ProviderMediaReferenceResolver,
    ProviderMediaResolutionError,
    ProviderMediaResolverConfig,
)
from tests.fakes.object_storage import FakeObjectStorage

PNG_BYTES = b"\x89PNG\r\n\x1a\nprovider-media-test"


class FakeAssetReader:
    def __init__(self, record: ProviderMediaAssetVersion | None) -> None:
        self.record = record
        self.calls: list[tuple[UUID, UUID]] = []

    def get_clean_image_version(
        self,
        *,
        organization_id: UUID,
        file_version_id: UUID,
    ) -> ProviderMediaAssetVersion | None:
        self.calls.append((organization_id, file_version_id))
        return self.record


def test_resolver_materializes_only_a_clean_tenant_scoped_image(
    tmp_path: Path,
) -> None:
    organization_id = uuid4()
    version_id = uuid4()
    storage = FakeObjectStorage()
    record = _record(organization_id=organization_id, version_id=version_id)
    storage.put_bytes(
        bucket=record.storage_bucket,
        key=record.storage_key,
        payload=PNG_BYTES,
        media_type=record.mime_type,
    )
    reader = FakeAssetReader(record)
    resolver = _resolver(tmp_path, reader, storage)

    url = resolver.resolve(
        organization_id=organization_id,
        reference=MediaReference(file_version_id=version_id, mime_type="image/png"),
    )

    parsed = urlsplit(url)
    files = list(tmp_path.iterdir())
    assert parsed.scheme == "https"
    assert parsed.netloc == "newapi.doitbenai.cloud"
    assert parsed.path.startswith("/_shanhai-provider-media/")
    assert len(files) == 1
    assert files[0].suffix == ".png"
    assert files[0].read_bytes() == PNG_BYTES
    assert record.storage_key not in url
    assert reader.calls == [(organization_id, version_id)]


def test_resolver_fails_closed_without_a_validated_asset(
    tmp_path: Path,
) -> None:
    storage = FakeObjectStorage()
    resolver = _resolver(tmp_path, FakeAssetReader(None), storage)

    with pytest.raises(ProviderMediaResolutionError, match="unavailable"):
        resolver.resolve(
            organization_id=uuid4(),
            reference=MediaReference(file_version_id=uuid4(), mime_type="image/png"),
        )

    assert list(tmp_path.iterdir()) == []


def test_resolver_rejects_mismatched_or_tampered_object_bytes(tmp_path: Path) -> None:
    organization_id = uuid4()
    version_id = uuid4()
    record = _record(
        organization_id=organization_id,
        version_id=version_id,
        sha256="f" * 64,
    )
    storage = FakeObjectStorage()
    storage.put_bytes(
        bucket=record.storage_bucket,
        key=record.storage_key,
        payload=PNG_BYTES,
        media_type=record.mime_type,
    )
    resolver = _resolver(tmp_path, FakeAssetReader(record), storage)

    with pytest.raises(ProviderMediaResolutionError, match="integrity"):
        resolver.resolve(
            organization_id=organization_id,
            reference=MediaReference(file_version_id=version_id, mime_type="image/png"),
        )

    assert list(tmp_path.iterdir()) == []


def test_resolver_rejects_mismatched_object_storage_media_type(tmp_path: Path) -> None:
    organization_id = uuid4()
    version_id = uuid4()
    record = _record(organization_id=organization_id, version_id=version_id)
    storage = FakeObjectStorage()
    storage.put_bytes(
        bucket=record.storage_bucket,
        key=record.storage_key,
        payload=PNG_BYTES,
        media_type="application/octet-stream",
    )
    resolver = _resolver(tmp_path, FakeAssetReader(record), storage)

    with pytest.raises(ProviderMediaResolutionError, match="integrity"):
        resolver.resolve(
            organization_id=organization_id,
            reference=MediaReference(file_version_id=version_id, mime_type="image/png"),
        )

    assert list(tmp_path.iterdir()) == []


def test_resolver_removes_materialized_file_when_the_provider_url_is_too_long(
    tmp_path: Path,
) -> None:
    organization_id = uuid4()
    version_id = uuid4()
    record = _record(organization_id=organization_id, version_id=version_id)
    storage = FakeObjectStorage()
    storage.put_bytes(
        bucket=record.storage_bucket,
        key=record.storage_key,
        payload=PNG_BYTES,
        media_type=record.mime_type,
    )
    resolver = _resolver(
        tmp_path,
        FakeAssetReader(record),
        storage,
        public_base_url=f"https://relay.test/{'a' * 4096}",
    )

    with pytest.raises(ProviderMediaResolutionError, match="URL exceeds"):
        resolver.resolve(
            organization_id=organization_id,
            reference=MediaReference(file_version_id=version_id, mime_type="image/png"),
        )

    assert list(tmp_path.iterdir()) == []


def test_resolver_removes_only_expired_opaque_relay_files(tmp_path: Path) -> None:
    stale = tmp_path / f"{'a' * 32}.png"
    stale.write_bytes(PNG_BYTES)
    os.utime(stale, (time() - 61, time() - 61))
    keep = tmp_path / "operator-note.txt"
    keep.write_text("preserve", encoding="utf-8")
    resolver = _resolver(tmp_path, FakeAssetReader(None), FakeObjectStorage(), ttl_seconds=60)

    removed = resolver.cleanup_expired(now=time())

    assert removed == 1
    assert not stale.exists()
    assert keep.read_text(encoding="utf-8") == "preserve"


def _resolver(
    root: Path,
    reader: FakeAssetReader,
    storage: FakeObjectStorage,
    *,
    ttl_seconds: int = 60,
    public_base_url: str = "https://newapi.doitbenai.cloud/_shanhai-provider-media",
) -> ProviderMediaReferenceResolver:
    return ProviderMediaReferenceResolver(
        asset_reader=reader,
        storage=storage,
        config=ProviderMediaResolverConfig(
            relay_root=root,
            public_base_url=public_base_url,
            signing_secret=hashlib.sha256(b"provider-media-test").hexdigest(),
            ttl_seconds=ttl_seconds,
            max_file_bytes=1024,
        ),
    )


def _record(
    *,
    organization_id: UUID,
    version_id: UUID,
    sha256: str | None = None,
) -> ProviderMediaAssetVersion:
    return ProviderMediaAssetVersion(
        id=version_id,
        organization_id=organization_id,
        storage_bucket="shanhai-test",
        storage_key="immutable/test/image.png",
        mime_type="image/png",
        byte_size=len(PNG_BYTES),
        sha256=sha256 or hashlib.sha256(PNG_BYTES).hexdigest(),
    )
