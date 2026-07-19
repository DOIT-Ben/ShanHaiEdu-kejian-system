#!/usr/bin/env python3
"""Build the current frontend handoff ZIP from canonical repository files."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "deliverables" / "shanhaiedu-frontend-package.zip"
PACKAGE_ROOT = "shanhaiedu-frontend-package"
ROOT_FILES = {"AGENTS.md", "CURRENT_STATUS.md", "README.md"}
REQUIRED_FILES = ROOT_FILES | {
    "contracts/README.md",
    "docs/START_HERE.md",
    "docs/frontend/manifest.json",
    "docs/vendor/FRONTEND_KICKOFF_INSTRUCTION.md",
}


def _tracked_files() -> list[PurePosixPath]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return sorted(PurePosixPath(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw)


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


def _source_paths() -> list[PurePosixPath]:
    paths = [path for path in _tracked_files() if _is_packaged(path)]
    present = {path.as_posix() for path in paths}
    missing = sorted(REQUIRED_FILES - present)
    if missing:
        raise ValueError(f"frontend package is missing required sources: {missing}")
    return paths


def _canonical_bytes(path: PurePosixPath) -> bytes:
    data = (ROOT / Path(*path.parts)).read_bytes()
    if b"\0" in data:
        raise ValueError(f"frontend package source must be text: {path}")
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _source_date(files: dict[str, bytes]) -> date:
    metadata = json.loads(files["docs/frontend/manifest.json"])
    value = metadata.get("updated_at")
    if not isinstance(value, str):
        raise ValueError("docs/frontend/manifest.json must define updated_at")
    return date.fromisoformat(value)


def _source_digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for path, data in sorted(files.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def _zip_info(name: str, generated_on: date) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(
        filename=f"{PACKAGE_ROOT}/{name}",
        date_time=(generated_on.year, generated_on.month, generated_on.day, 0, 0, 0),
    )
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_archive() -> bytes:
    sources = {path.as_posix(): _canonical_bytes(path) for path in _source_paths()}
    generated_on = _source_date(sources)
    source_digest = _source_digest(sources)
    package_manifest = {
        "entry": "README.md",
        "file_count": len(sources),
        "generated_on": generated_on.isoformat(),
        "package": PACKAGE_ROOT,
        "schema_version": 1,
        "scope": [
            "current product and workflow documents",
            "frontend, backend and governance handoff documents",
            "OpenAPI, JSON Schema, generated TypeScript and golden fixtures",
        ],
        "source_tree_sha256": source_digest,
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the committed package differs from current canonical files",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    expected = build_archive()
    output = args.output.resolve()
    if args.check:
        if not output.is_file() or output.read_bytes() != expected:
            print(
                "frontend package is stale; run 'uv run python scripts/build_frontend_package.py'",
                file=sys.stderr,
            )
            return 1
        print("frontend package matches current canonical sources")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".zip.tmp")
    temporary.write_bytes(expected)
    temporary.replace(output)
    print(f"wrote {output} ({len(expected)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
