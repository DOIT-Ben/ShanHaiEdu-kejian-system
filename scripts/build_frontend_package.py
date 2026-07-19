#!/usr/bin/env python3
"""Build the current frontend handoff ZIP from canonical repository files."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import stat
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "deliverables" / "shanhaiedu-frontend-package.zip"
SNAPSHOT = ROOT / "deliverables" / "shanhaiedu-frontend-package.snapshot.json"
PACKAGE_ROOT = "shanhaiedu-frontend-package"
ROOT_FILES = {"AGENTS.md", "CURRENT_STATUS.md", "README.md"}
REGULAR_GIT_MODES = {"100644", "100755"}
TEXT_SUFFIXES = {
    ".css",
    ".example",
    ".json",
    ".md",
    ".sha256",
    ".ts",
    ".yaml",
    ".yml",
}
REQUIRED_FILES = ROOT_FILES | {
    "contracts/README.md",
    "contracts/api-surface.openapi.yaml",
    "contracts/planned-api-surface.openapi.yaml",
    "contracts/fixtures/primary-math-courseware-package/manifest.json",
    "contracts/generated/openapi.bundle.yaml",
    "contracts/generated/typescript/schema.ts",
    "docs/START_HERE.md",
    "docs/frontend/CHECKSUMS.sha256",
    "docs/frontend/manifest.json",
    "docs/vendor/FRONTEND_KICKOFF_INSTRUCTION.md",
    "docs/workflows/generation-guide/README.md",
}


@dataclass(frozen=True)
class TrackedFile:
    path: PurePosixPath
    mode: str
    stage: str


def _tracked_files(root: Path = ROOT) -> list[TrackedFile]:
    result = subprocess.run(
        ["git", "ls-files", "-s", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    tracked: list[TrackedFile] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            header, encoded_path = raw.split(b"\t", maxsplit=1)
            mode, _object_id, stage = header.split(b" ", maxsplit=2)
            path = PurePosixPath(encoded_path.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("git returned an invalid tracked-file record") from exc
        tracked.append(
            TrackedFile(
                path=path,
                mode=mode.decode("ascii"),
                stage=stage.decode("ascii"),
            )
        )
    return sorted(tracked, key=lambda item: item.path.as_posix())


def _is_packaged(path: PurePosixPath) -> bool:
    value = path.as_posix()
    if value in ROOT_FILES or value == "docs/START_HERE.md":
        return True
    if value == "docs/vendor/FRONTEND_KICKOFF_INSTRUCTION.md":
        return True
    if value.startswith("contracts/"):
        return True
    return any(
        value.startswith(prefix)
        for prefix in (
            "docs/backend/",
            "docs/frontend/",
            "docs/governance/",
            "docs/product/",
            "docs/workflows/",
        )
    )


def _source_entries(root: Path = ROOT) -> list[TrackedFile]:
    entries = [entry for entry in _tracked_files(root) if _is_packaged(entry.path)]
    for entry in entries:
        if entry.stage != "0" or entry.mode not in REGULAR_GIT_MODES:
            raise ValueError(
                "frontend package sources must be regular Git files: "
                f"{entry.path} (mode={entry.mode}, stage={entry.stage})"
            )
    present = {entry.path.as_posix() for entry in entries}
    missing = sorted(REQUIRED_FILES - present)
    if missing:
        raise ValueError(f"frontend package is missing required sources: {missing}")
    return entries


def _source_paths(root: Path = ROOT) -> list[PurePosixPath]:
    return [entry.path for entry in _source_entries(root)]


def _canonical_bytes(root: Path, path: PurePosixPath) -> bytes:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        raise ValueError(f"frontend package source has unsupported text extension: {path}")

    repository = root.resolve(strict=True)
    candidate = root.joinpath(*path.parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"frontend package source is unavailable: {path}") from exc
    if not resolved.is_relative_to(repository):
        raise ValueError(f"frontend package source resolves outside repository: {path}")
    if not stat.S_ISREG(candidate.lstat().st_mode):
        raise ValueError(f"frontend package source must be a regular file: {path}")

    try:
        text = resolved.read_bytes().decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"frontend package source must be valid UTF-8: {path}") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _collect_sources(root: Path = ROOT) -> dict[str, bytes]:
    return {
        entry.path.as_posix(): _canonical_bytes(root, entry.path) for entry in _source_entries(root)
    }


def _source_digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for path, data in sorted(files.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def _parse_snapshot(snapshot: dict[str, Any]) -> dict[str, str | int]:
    required = {"generated_on_utc", "source_file_count", "source_tree_sha256"}
    if set(snapshot) != required:
        raise ValueError("frontend package snapshot metadata has invalid fields")

    generated_on_utc = snapshot["generated_on_utc"]
    source_file_count = snapshot["source_file_count"]
    source_tree_sha256 = snapshot["source_tree_sha256"]
    if not isinstance(generated_on_utc, str):
        raise ValueError("frontend package snapshot timestamp must be a string")
    try:
        generated_at = datetime.fromisoformat(generated_on_utc.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError("frontend package snapshot timestamp is invalid") from exc
    canonical_timestamp = (
        generated_at.astimezone(UTC)
        .replace(microsecond=0)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    if generated_at.utcoffset() != UTC.utcoffset(None) or canonical_timestamp != generated_on_utc:
        raise ValueError("frontend package snapshot timestamp must be canonical UTC")
    if (
        not isinstance(source_file_count, int)
        or isinstance(source_file_count, bool)
        or source_file_count < 0
    ):
        raise ValueError("frontend package snapshot file count is invalid")
    if (
        not isinstance(source_tree_sha256, str)
        or len(source_tree_sha256) != 64
        or any(character not in "0123456789abcdef" for character in source_tree_sha256)
    ):
        raise ValueError("frontend package snapshot digest is invalid")
    return {
        "generated_on_utc": generated_on_utc,
        "source_file_count": source_file_count,
        "source_tree_sha256": source_tree_sha256,
    }


def _snapshot_for_sources(
    sources: dict[str, bytes],
    snapshot: dict[str, Any],
) -> dict[str, str | int]:
    parsed = _parse_snapshot(snapshot)
    if parsed["source_file_count"] != len(sources) or parsed[
        "source_tree_sha256"
    ] != _source_digest(sources):
        raise ValueError("frontend package snapshot metadata is stale")
    return parsed


def _read_snapshot(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("frontend package snapshot metadata is unreadable") from exc
    if not isinstance(value, dict):
        raise ValueError("frontend package snapshot metadata must be an object")
    return cast(dict[str, Any], value)


def _current_snapshot(
    sources: dict[str, bytes],
    snapshot_path: Path = SNAPSHOT,
) -> dict[str, str | int]:
    return _snapshot_for_sources(sources, _read_snapshot(snapshot_path))


def _select_snapshot(
    sources: dict[str, bytes],
    *,
    previous: dict[str, Any] | None,
    now: datetime,
) -> dict[str, str | int]:
    if previous is not None:
        try:
            return _snapshot_for_sources(sources, previous)
        except ValueError:
            pass
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("frontend package snapshot time must be timezone-aware")
    generated_on_utc = (
        now.astimezone(UTC)
        .replace(microsecond=0)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    return {
        "generated_on_utc": generated_on_utc,
        "source_file_count": len(sources),
        "source_tree_sha256": _source_digest(sources),
    }


def _zip_info(name: str, generated_on: date) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(
        filename=f"{PACKAGE_ROOT}/{name}",
        date_time=(generated_on.year, generated_on.month, generated_on.day, 0, 0, 0),
    )
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _build_archive(
    sources: dict[str, bytes],
    snapshot: dict[str, Any],
) -> bytes:
    current_snapshot = _snapshot_for_sources(sources, snapshot)
    generated_at = datetime.fromisoformat(
        str(current_snapshot["generated_on_utc"]).removesuffix("Z") + "+00:00"
    )
    generated_on = generated_at.date()
    package_manifest = {
        "entry": "README.md",
        "generated_on": generated_on.isoformat(),
        "generated_on_utc": current_snapshot["generated_on_utc"],
        "package": PACKAGE_ROOT,
        "schema_version": 1,
        "scope": [
            "current product and workflow documents",
            "frontend, backend and governance handoff documents",
            "OpenAPI, JSON Schema, generated TypeScript and golden fixtures",
        ],
        "source_file_count": current_snapshot["source_file_count"],
        "source_tree_sha256": current_snapshot["source_tree_sha256"],
    }
    packaged = dict(sources)
    packaged["PACKAGE_MANIFEST.json"] = (
        json.dumps(
            package_manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    checksum_lines = [
        f"{hashlib.sha256(data).hexdigest()}  ./{path}" for path, data in sorted(packaged.items())
    ]
    packaged["CHECKSUMS.sha256"] = ("\n".join(checksum_lines) + "\n").encode()

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path, data in sorted(packaged.items()):
            archive.writestr(
                _zip_info(path, generated_on),
                data,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return buffer.getvalue()


def build_archive(snapshot_path: Path = SNAPSHOT) -> bytes:
    sources = _collect_sources()
    return _build_archive(sources, _current_snapshot(sources, snapshot_path))


def _snapshot_bytes(snapshot: dict[str, Any]) -> bytes:
    return (
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the committed package differs from current canonical files",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    args = parser.parse_args()

    output = args.output.resolve()
    snapshot_path = args.snapshot.resolve()
    sources = _collect_sources()
    if args.check:
        try:
            snapshot = _current_snapshot(sources, snapshot_path)
            expected = _build_archive(sources, snapshot)
        except ValueError:
            expected = None
        if expected is None or not output.is_file() or output.read_bytes() != expected:
            print(
                "frontend package or snapshot metadata is stale; "
                "run 'uv run python scripts/build_frontend_package.py'",
                file=sys.stderr,
            )
            return 1
        print("frontend package matches current canonical sources")
        return 0

    try:
        previous = _read_snapshot(snapshot_path) if snapshot_path.is_file() else None
    except ValueError:
        previous = None
    snapshot = _select_snapshot(sources, previous=previous, now=datetime.now(UTC))
    expected = _build_archive(sources, snapshot)
    _write_atomic(output, expected)
    _write_atomic(snapshot_path, _snapshot_bytes(snapshot))
    print(f"wrote {output} ({len(expected)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
