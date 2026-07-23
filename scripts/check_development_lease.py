#!/usr/bin/env python3
"""Fail pull requests that modify files outside their declared development track."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRACK_PATTERN = re.compile(r"(?im)^\s*development-track:\s*`?([a-z][a-z0-9_]*)`?\s*$")


def _load_leases(root: Path = ROOT) -> dict[str, Any]:
    path = root / "contracts/development-leases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def parse_development_track(body: str) -> str | None:
    matches = TRACK_PATTERN.findall(body)
    return matches[0] if len(matches) == 1 else None


def _matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path, pattern)


def validate_changed_paths(
    leases: dict[str, Any],
    track_key: str,
    changed_paths: list[str],
) -> list[str]:
    tracks = {
        track.get("track_key"): track
        for track in leases.get("tracks", [])
        if isinstance(track, dict)
    }
    track = tracks.get(track_key)
    if track is None:
        return [f"unknown development track: {track_key}"]

    writable = track.get("writable", [])
    readonly = track.get("readonly", [])
    forbidden = track.get("forbidden", [])
    errors: list[str] = []
    for path in sorted(set(changed_paths)):
        blocked_by = [pattern for pattern in [*readonly, *forbidden] if _matches(path, pattern)]
        if blocked_by:
            errors.append(f"{track_key} track cannot modify {path}; protected by {blocked_by}")
            continue
        if not any(_matches(path, pattern) for pattern in writable):
            errors.append(f"{track_key} track has no writable lease for changed path: {path}")
    return errors


def _decode_git_path(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogateescape")


def _parse_name_status(output: bytes) -> list[str]:
    tokens = output.split(b"\0")
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        status_token = tokens[index]
        index += 1
        if not status_token:
            break
        status = status_token.decode("ascii", errors="strict")
        if status.startswith(("R", "C")):
            if index + 1 >= len(tokens):
                raise ValueError(f"malformed git rename/copy output for status {status}")
            paths.append(_decode_git_path(tokens[index]))
            paths.append(_decode_git_path(tokens[index + 1]))
            index += 2
            continue
        if index >= len(tokens):
            raise ValueError(f"malformed git diff output for status {status}")
        paths.append(_decode_git_path(tokens[index]))
        index += 1
    return paths


def _changed_paths(base_sha: str, head_sha: str, root: Path = ROOT) -> list[str]:
    command = [
        "git",
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        "--find-copies",
        "--diff-filter=ACMRD",
        f"{base_sha}...{head_sha}",
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        check=True,
        capture_output=True,
    )
    return _parse_name_status(completed.stdout)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Pull request base commit SHA")
    parser.add_argument("--head", required=True, help="Pull request head commit SHA")
    parser.add_argument(
        "--body-env",
        default="PR_BODY",
        help="Environment variable containing the pull request body",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    body = os.environ.get(args.body_env, "")
    track_key = parse_development_track(body)
    if track_key is None:
        print(
            "error: pull request body must contain exactly one `development-track: <track>`",
            file=sys.stderr,
        )
        return 1

    try:
        changed_paths = _changed_paths(args.base, args.head)
        errors = validate_changed_paths(_load_leases(), track_key, changed_paths)
    except (
        json.JSONDecodeError,
        KeyError,
        OSError,
        UnicodeDecodeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"error: development lease validation failed: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"development lease checks passed for {track_key}: {len(set(changed_paths))} paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
