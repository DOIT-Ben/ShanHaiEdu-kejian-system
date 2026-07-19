#!/usr/bin/env python3
"""Verify the pinned Linux development container and filesystem behavior."""

from __future__ import annotations

import os
import platform
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

CommandRunner = Callable[[list[str]], str]

EXPECTED_VERSION_PREFIXES = {
    "python": "Python 3.12.12",
    "uv": "uv 0.10.6",
    "node": "v22.22.0",
    "pnpm": "10.30.2",
    "git": "git version ",
    "ffmpeg": "ffmpeg version ",
    "libreoffice": "LibreOffice ",
}

VERSION_COMMANDS = {
    "python": ["python", "--version"],
    "uv": ["uv", "--version"],
    "node": ["node", "--version"],
    "pnpm": ["pnpm", "--version"],
    "git": ["git", "--version"],
    "ffmpeg": ["ffmpeg", "-version"],
    "libreoffice": ["libreoffice", "--version"],
}


def run_version_command(command: list[str]) -> str:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    output = (result.stdout or result.stderr).strip().splitlines()
    if result.returncode != 0 or not output:
        rendered = " ".join(command)
        raise RuntimeError(f"version command failed: {rendered}")
    return output[0]


def collect_versions(runner: CommandRunner = run_version_command) -> dict[str, str]:
    return {name: runner(command) for name, command in VERSION_COMMANDS.items()}


def validate_versions(versions: dict[str, str]) -> list[str]:
    errors = []
    for name, prefix in EXPECTED_VERSION_PREFIXES.items():
        actual = versions.get(name, "missing")
        if not actual.startswith(prefix):
            errors.append(f"{name}: expected prefix {prefix!r}, got {actual!r}")
    return errors


def verify_filesystem(root: Path) -> None:
    target = root / "symlink-target.txt"
    link = root / "symlink-check.txt"
    target.write_text("linux-symlink-ok", encoding="utf-8")
    link.symlink_to(target.name)
    if link.read_text(encoding="utf-8") != "linux-symlink-ok":
        raise RuntimeError("symbolic link verification failed")

    nested = root
    while len(str(nested)) < 320:
        nested /= "long-path-segment"
        nested.mkdir()
    marker = nested / "marker.txt"
    marker.write_text("linux-long-path-ok", encoding="utf-8")
    if marker.read_text(encoding="utf-8") != "linux-long-path-ok":
        raise RuntimeError("long path verification failed")


def verify_workspace_write(root: Path) -> None:
    marker = root / f".shanhai-workspace-write-{os.getpid()}"
    try:
        marker.write_text("workspace-write-ok", encoding="utf-8")
        if marker.read_text(encoding="utf-8") != "workspace-write-ok":
            raise RuntimeError("workspace write verification failed")
    finally:
        marker.unlink(missing_ok=True)


def main() -> int:
    errors = []
    rootless_userns = os.getenv("SHANHAI_CONTAINER_ROOTLESS_USERNS", "false") == "true"
    if platform.system() != "Linux":
        errors.append(f"expected Linux, got {platform.system()}")
    if hasattr(os, "geteuid") and os.geteuid() == 0 and not rootless_userns:
        errors.append("workspace commands must not run as root")
    if hasattr(os, "geteuid") and os.geteuid() != 0 and rootless_userns:
        errors.append("rootless Docker workspace must run as container root")

    try:
        versions = collect_versions()
        errors.extend(validate_versions(versions))
    except RuntimeError as exc:
        versions = {}
        errors.append(str(exc))

    try:
        with tempfile.TemporaryDirectory(prefix="shanhai-linux-check-") as directory:
            verify_filesystem(Path(directory))
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))

    try:
        verify_workspace_write(Path(__file__).resolve().parents[1])
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    for name, version in versions.items():
        print(f"PASS: {name}={version}")
    identity = "rootless user namespace" if rootless_userns else "non-root container user"
    print(f"PASS: {identity}, workspace write, symbolic links and long paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
