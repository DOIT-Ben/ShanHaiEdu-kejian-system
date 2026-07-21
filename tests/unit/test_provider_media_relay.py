from __future__ import annotations

import base64
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from apps.api.provider_media_relay import (
    ProviderMediaRelayConfig,
    ProviderMediaRelayServer,
    ProviderMediaRequestError,
    resolve_media_request,
    sign_media_path,
)

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mNk+M/wHwAF/gL+3MxZ5wAAAABJRU5ErkJggg=="
)


def relay_config(root: Path, *, max_file_bytes: int = 1_024) -> ProviderMediaRelayConfig:
    return ProviderMediaRelayConfig(
        root=root,
        signing_secret="test-placeholder-provider-media-signing-secret",
        max_ttl_seconds=300,
        max_file_bytes=max_file_bytes,
    )


def test_valid_signed_image_resolves_to_a_private_file(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(PNG_BYTES)
    config = relay_config(tmp_path)
    path = sign_media_path("frame.png", expires_at=1_100, secret=config.signing_secret)

    asset = resolve_media_request(path, config, now=1_000)

    assert asset.path == image
    assert asset.media_type == "image/png"
    assert asset.size_bytes == len(PNG_BYTES)
    assert asset.content == PNG_BYTES


@pytest.mark.parametrize(
    "path",
    [
        "/frame.png?expires=999&signature=ignored",
        "/frame.png?expires=1301&signature=ignored",
        "/../secret.png?expires=1100&signature=ignored",
    ],
)
def test_invalid_expiry_or_unsafe_path_fails_closed(tmp_path: Path, path: str) -> None:
    config = relay_config(tmp_path)

    with pytest.raises(ProviderMediaRequestError):
        resolve_media_request(path, config, now=1_000)


def test_tampered_signature_fails_closed(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(PNG_BYTES)
    config = relay_config(tmp_path)
    path = sign_media_path("frame.png", expires_at=1_100, secret=config.signing_secret)
    tampered = path.replace("signature=", "signature=altered")

    with pytest.raises(ProviderMediaRequestError):
        resolve_media_request(tampered, config, now=1_000)


def test_non_image_and_oversized_files_fail_closed(tmp_path: Path) -> None:
    text_file = tmp_path / "frame.txt"
    text_file.write_text("not an image", encoding="utf-8")
    large_image = tmp_path / "large.png"
    large_image.write_bytes(PNG_BYTES + b"x" * 20)
    config = relay_config(tmp_path, max_file_bytes=10)

    for filename in ("frame.txt", "large.png"):
        path = sign_media_path(filename, expires_at=1_100, secret=config.signing_secret)
        with pytest.raises(ProviderMediaRequestError):
            resolve_media_request(path, config, now=1_000)


def test_extension_must_match_detected_image_type(tmp_path: Path) -> None:
    disguised_image = tmp_path / "frame.jpg"
    disguised_image.write_bytes(PNG_BYTES)
    config = relay_config(tmp_path)
    path = sign_media_path("frame.jpg", expires_at=1_100, secret=config.signing_secret)

    with pytest.raises(ProviderMediaRequestError):
        resolve_media_request(path, config, now=1_000)


def test_symlink_to_file_outside_relay_root_fails_closed(tmp_path: Path) -> None:
    external_image = tmp_path.parent / "provider-media-relay-external.png"
    external_image.write_bytes(PNG_BYTES)
    linked_image = tmp_path / "frame.png"
    try:
        linked_image.symlink_to(external_image)
    except OSError:
        external_image.unlink()
        pytest.skip("symbolic links require a Windows developer privilege")
    config = relay_config(tmp_path)
    path = sign_media_path("frame.png", expires_at=1_100, secret=config.signing_secret)

    try:
        with pytest.raises(ProviderMediaRequestError):
            resolve_media_request(path, config, now=1_000)
    finally:
        external_image.unlink()


def test_http_relay_serves_valid_image_without_caching(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(PNG_BYTES)
    config = relay_config(tmp_path)
    server = ProviderMediaRelayServer(("127.0.0.1", 0), config)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    path = sign_media_path(
        "frame.png",
        expires_at=int(__import__("time").time()) + 30,
        secret=config.signing_secret,
    )
    host = str(server.server_address[0])
    port = int(server.server_address[1])

    try:
        with urlopen(f"http://{host}:{port}{path}") as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "image/png"
            assert response.headers["Cache-Control"] == "no-store"
            assert response.read() == PNG_BYTES
        with pytest.raises(HTTPError) as response:
            urlopen(f"http://{host}:{port}{path}x")
        assert response.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
