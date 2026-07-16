#!/usr/bin/env python3
"""Scan tracked text files for high-confidence credential patterns without echoing values."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIPPED_SUFFIXES = {".lock", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pptx", ".zip"}
SKIPPED_DIRECTORIES = {"deliverables"}
ALLOWED_MARKERS = ("example", "local-only", "placeholder", "change-me", "${")
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "quoted_secret": re.compile(
        r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]([A-Za-z0-9_./+=-]{16,})['\"]"
    ),
    "environment_secret": re.compile(
        r"^[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD)[A-Z0-9_]*=([A-Za-z0-9_./+=-]{16,})$"
    ),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths = [ROOT / part.decode("utf-8") for part in result.stdout.split(b"\0") if part]
    return [path for path in paths if path.is_file()]


def scan_text(path: Path, text: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        for label, pattern in PATTERNS.items():
            if not pattern.search(line):
                continue
            if label in {"quoted_secret", "environment_secret"} and any(
                marker in lowered for marker in ALLOWED_MARKERS
            ):
                continue
            findings.append((line_number, label))
    return findings


def main() -> int:
    findings: list[tuple[Path, int, str]] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT)
        if relative.parts[0] in SKIPPED_DIRECTORIES or path.suffix.lower() in SKIPPED_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        findings.extend((relative, line, label) for line, label in scan_text(path, text))

    if findings:
        for path, line, label in findings:
            print(f"potential secret: {path}:{line} ({label})", file=sys.stderr)
        return 1
    print(f"tracked secret scan passed for {len(tracked_files())} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
