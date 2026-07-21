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
    cleanup_expired_provider_media,
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


@pytest.mark.parametrize(
    "secret",
    [
        "",
        "a1" * 31 + "a",
        "a1" * 32 + "a",
        "g1" * 32,
        "a" * 64,
        "0123456789abcdef" * 4,
        "PLACEHOLDER_REPLACE_WITH_A_UNIQUE_64_HEX_CHARACTER_SECRET",
    ],
)
def test_resolver_rejects_invalid_signing_secret_without_disclosure(
    tmp_path: Path,
    secret: str,
) -> None:
    with pytest.raises(ValueError) as error:
        ProviderMediaResolverConfig(
            relay_root=tmp_path,
            public_base_url="https://relay.test/provider-media",
            signing_secret=secret,
            ttl_seconds=60,
            max_file_bytes=1_024,
        )

    assert "signing_secret is invalid" in str(error.value)
    if secret:
        assert secret not in str(error.value)


def test_resolver_accepts_mixed_case_64_hex_secret_without_normalizing(tmp_path: Path) -> None:
    secret = "Aa1b" * 16

    config = ProviderMediaResolverConfig(
        relay_root=tmp_path,
        public_base_url="https://relay.test/provider-media",
        signing_secret=secret,
        ttl_seconds=60,
        max_file_bytes=1_024,
    )

    assert config.signing_secret == secret


def test_resolver_removes_only_expired_opaque_relay_files(tmp_path: Path) -> None:
    stale = tmp_path / f"{'a' * 32}.png"
    stale.write_bytes(PNG_BYTES)
    os.utime(stale, (time() - 61, time() - 61))
    stale_partial = tmp_path / f".provider-media-{'b' * 32}.partial"
    stale_partial.write_bytes(PNG_BYTES)
    os.utime(stale_partial, (time() - 61, time() - 61))
    keeps = [tmp_path / f"operator-note-{index}.txt" for index in range(3)]
    for keep in keeps:
        keep.write_text("preserve", encoding="utf-8")
    resolver = _resolver(tmp_path, FakeAssetReader(None), FakeObjectStorage(), ttl_seconds=60)

    removed = resolver.cleanup_expired(now=time())

    assert removed == 2
    assert not stale.exists()
    assert not stale_partial.exists()
    assert all(keep.read_text(encoding="utf-8") == "preserve" for keep in keeps)


def test_cleanup_limit_counts_candidates_not_unrelated_files(tmp_path: Path) -> None:
    for index in range(3):
        (tmp_path / f"unrelated-{index}.txt").write_text("preserve", encoding="utf-8")
    stale = tmp_path / f"{'c' * 32}.webp"
    stale.write_bytes(PNG_BYTES)
    os.utime(stale, (time() - 61, time() - 61))

    removed = cleanup_expired_provider_media(
        tmp_path,
        ttl_seconds=60,
        now=time(),
        scan_limit=1,
    )

    assert removed == 1
    assert not stale.exists()


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
