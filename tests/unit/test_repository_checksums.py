from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.check_repository import check_checksum_manifest


def test_checksum_manifest_normalizes_windows_line_endings(tmp_path: Path) -> None:
    target = tmp_path / "document.md"
    target.write_bytes(b"first\r\nsecond\r\n")
    expected = hashlib.sha256(b"first\nsecond\n").hexdigest()
    manifest = tmp_path / "CHECKSUMS.sha256"
    manifest.write_text(f"{expected}  ./document.md\n", encoding="utf-8")
    errors: list[str] = []

    check_checksum_manifest(manifest, errors)

    assert errors == []


def test_checksum_manifest_rejects_content_drift(tmp_path: Path) -> None:
    target = tmp_path / "document.md"
    target.write_text("changed\n", encoding="utf-8")
    manifest = tmp_path / "CHECKSUMS.sha256"
    manifest.write_text(f"{'0' * 64}  ./document.md\n", encoding="utf-8")
    errors: list[str] = []

    check_checksum_manifest(manifest, errors)

    assert errors == ["checksum mismatch: document.md"]


def test_checksum_manifest_does_not_normalize_binary_assets(tmp_path: Path) -> None:
    target = tmp_path / "asset.bin"
    target.write_bytes(b"first\r\nsecond\r\n")
    expected = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = tmp_path / "CHECKSUMS.sha256"
    manifest.write_text(f"{expected}  ./asset.bin\n", encoding="utf-8")
    errors: list[str] = []

    check_checksum_manifest(manifest, errors)

    assert errors == []
