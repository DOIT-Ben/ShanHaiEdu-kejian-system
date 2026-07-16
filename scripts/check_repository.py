#!/usr/bin/env python3
"""Validate the active repository tree without creating new artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

try:
    import yaml
except ImportError:  # pragma: no cover - reported as a repository setup error
    yaml = None


ROOT = Path(__file__).resolve().parents[1]

REQUIRED = {
    "README.md",
    "AGENTS.md",
    "CURRENT_STATUS.md",
    "docs/START_HERE.md",
    "docs/governance/TEAM_WORKFLOW.md",
    "docs/governance/DOCUMENT_POLICY.md",
    "docs/governance/DELIVERY_ROADMAP.md",
    "contracts/api-surface.openapi.yaml",
}

FORBIDDEN_DIRECTORIES = {
    "docs/architecture",
    "docs/requirements",
    "docs/frontend-outsourcing",
    "docs/superpowers",
}

FORBIDDEN_NAME = re.compile(
    r"(^|[-_.])(v[0-9]+|final|latest|copy|backup)([-_.]|$)|^20[0-9]{2}-[0-9]{2}-[0-9]{2}",
    re.IGNORECASE,
)

MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FRONTEND_CHECKSUMS = ROOT / "docs/frontend/CHECKSUMS.sha256"
TEXT_CHECKSUM_SUFFIXES = {".css", ".json", ".md"}


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    files = [ROOT / part.decode() for part in result.stdout.split(b"\0") if part]
    return [path for path in files if path.is_file()]


def check_required(errors: list[str]) -> None:
    for relative in sorted(REQUIRED):
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")
    for relative in sorted(FORBIDDEN_DIRECTORIES):
        if (ROOT / relative).exists():
            errors.append(f"legacy directory remains: {relative}")


def check_names(files: list[Path], errors: list[str]) -> None:
    for path in files:
        relative = path.relative_to(ROOT)
        if relative.parts[0] in {"docs", "contracts"} and FORBIDDEN_NAME.search(path.name):
            errors.append(f"versioned or backup-style active filename: {relative}")


def check_json(files: list[Path], errors: list[str]) -> None:
    for path in files:
        if path.suffix != ".json":
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")


def check_yaml(files: list[Path], errors: list[str]) -> None:
    yaml_files = [path for path in files if path.suffix in {".yml", ".yaml"}]
    if not yaml_files:
        return
    if yaml is None:
        errors.append("PyYAML is required to validate repository YAML files")
        return
    for path in yaml_files:
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            errors.append(f"invalid YAML {path.relative_to(ROOT)}: {exc}")


def check_markdown_links(files: list[Path], errors: list[str]) -> None:
    for path in files:
        if path.suffix != ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read Markdown {path.relative_to(ROOT)}: {exc}")
            continue
        for raw in MARKDOWN_LINK.findall(text):
            target = raw.strip().split(" ", 1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:", "sandbox:")):
                continue
            target = unquote(target.split("#", 1)[0])
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                errors.append(f"link escapes repository: {path.relative_to(ROOT)} -> {raw}")
                continue
            if not resolved.exists():
                errors.append(f"broken link: {path.relative_to(ROOT)} -> {raw}")


def check_checksum_manifest(manifest: Path, errors: list[str]) -> None:
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"cannot read checksum manifest {manifest}: {exc}")
        return

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            expected, raw_target = line.split(maxsplit=1)
        except ValueError:
            errors.append(f"invalid checksum line {manifest}:{line_number}")
            continue
        target = (manifest.parent / raw_target.lstrip("*")).resolve()
        try:
            target.relative_to(manifest.parent.resolve())
        except ValueError:
            errors.append(f"checksum target escapes manifest directory: {raw_target}")
            continue
        try:
            content = target.read_bytes()
        except OSError as exc:
            errors.append(f"cannot read checksum target {target}: {exc}")
            continue
        if target.suffix in TEXT_CHECKSUM_SUFFIXES or target.name.endswith(".example"):
            content = content.replace(b"\r\n", b"\n")
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            errors.append(f"checksum mismatch: {target.relative_to(manifest.parent.resolve())}")


def report_size_triggers(files: list[Path]) -> None:
    for path in files:
        if path.suffix != ".md":
            continue
        try:
            line_count = len(path.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeError):
            continue
        if line_count > 300:
            print(
                f"warning: {path.relative_to(ROOT)} has {line_count} lines; "
                "split it or explain the exception in review",
                file=sys.stderr,
            )


def main() -> int:
    errors: list[str] = []
    files = repository_files()
    check_required(errors)
    check_names(files, errors)
    check_json(files, errors)
    check_yaml(files, errors)
    check_markdown_links(files, errors)
    check_checksum_manifest(FRONTEND_CHECKSUMS, errors)
    report_size_triggers(files)

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"repository policy checks passed for {len(files)} tracked files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
