#!/usr/bin/env python3
"""Validate a pull request's status and review evidence declarations."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

DECLARATION = re.compile(
    r"^-\s*\[[xX]\]\s*`(?P<choice>status-update-(?:required|not-required))`",
    re.MULTILINE,
)
REVIEW_MARKER = re.compile(r"`subagent-review-(?:pending|approved)`")
REVIEW_DECLARATION = re.compile(
    r"^-\s*\[(?P<checked>[ xX])\]\s*"
    r"`(?P<choice>subagent-review-(?:pending|approved))`",
    re.MULTILINE,
)
FULL_SHA = re.compile(r"[0-9a-fA-F]{40}")
SIZE_MARKER = re.compile(r"`pr-size-(?:within-limit|review-map-required)`")
SIZE_DECLARATION = re.compile(
    r"^-\s*\[(?P<checked>[ xX])\]\s*"
    r"`(?P<choice>pr-size-(?:within-limit|review-map-required))`",
    re.MULTILINE,
)


def validate_status_declaration(body: str, changed_files: set[str]) -> list[str]:
    choices = DECLARATION.findall(body)
    if len(choices) != 1:
        return ["PR must select exactly one CURRENT_STATUS freshness declaration"]

    changes_status = "CURRENT_STATUS.md" in {path.replace("\\", "/") for path in changed_files}
    if choices[0] == "status-update-required" and not changes_status:
        return ["PR declares status-update-required but does not change CURRENT_STATUS.md"]
    if choices[0] == "status-update-not-required" and changes_status:
        return ["PR changes CURRENT_STATUS.md but declares status-update-not-required"]
    return []


def _review_field(body: str, label: str) -> str:
    field = re.search(
        rf"^\s*{re.escape(label)}\s*[\uFF1A:]\s*(?P<value>.*?)\s*$",
        body,
        re.MULTILINE,
    )
    if field is None:
        return ""
    return field.group("value").strip().strip("`").strip()


def validate_review_declaration(body: str, base_sha: str, head_sha: str) -> list[str]:
    if REVIEW_MARKER.search(body) is None:
        return []

    choices = [
        match.group("choice")
        for match in REVIEW_DECLARATION.finditer(body)
        if match.group("checked").lower() == "x"
    ]
    if len(choices) != 1:
        return ["PR must select exactly one subagent review declaration"]
    if choices[0] == "subagent-review-pending":
        return []

    errors: list[str] = []
    declared_base = _review_field(body, "Base SHA")
    declared_head = _review_field(body, "Head SHA")
    if FULL_SHA.fullmatch(declared_base) is None:
        errors.append("subagent-review-approved requires a full 40-character Base SHA")
    elif declared_base.lower() != base_sha.lower():
        errors.append("subagent review Base SHA does not match the pull request base SHA")
    if FULL_SHA.fullmatch(declared_head) is None:
        errors.append("subagent-review-approved requires a full 40-character Head SHA")
    elif declared_head.lower() != head_sha.lower():
        errors.append("subagent review Head SHA does not match the pull request head SHA")
    return errors


def validate_size_declaration(
    body: str,
    changed_file_count: int,
    additions: int,
    deletions: int,
) -> list[str]:
    if SIZE_MARKER.search(body) is None:
        return []

    choices = [
        match.group("choice")
        for match in SIZE_DECLARATION.finditer(body)
        if match.group("checked").lower() == "x"
    ]
    if len(choices) != 1:
        return ["PR must select exactly one pull request size declaration"]

    exceeds_raw_trigger = changed_file_count > 20 or additions - deletions > 800
    if exceeds_raw_trigger and choices[0] != "pr-size-review-map-required":
        return ["PR exceeds the raw size trigger but does not require a review map"]
    if not exceeds_raw_trigger and choices[0] != "pr-size-within-limit":
        return ["PR declares a required review map but does not exceed the raw size trigger"]
    return []


def changed_files(base_sha: str, head_sha: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def changed_line_counts(base_sha: str, head_sha: str) -> tuple[int, int]:
    result = subprocess.run(
        ["git", "diff", "--numstat", f"{base_sha}...{head_sha}"],
        check=True,
        capture_output=True,
        text=True,
    )
    additions = 0
    deletions = 0
    for line in result.stdout.splitlines():
        added, deleted, _path = line.split("\t", 2)
        if added.isdigit() and deleted.isdigit():
            additions += int(added)
            deletions += int(deleted)
    return additions, deletions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--body", required=True)
    args = parser.parse_args()

    files = changed_files(args.base_sha, args.head_sha)
    additions, deletions = changed_line_counts(args.base_sha, args.head_sha)
    errors = validate_status_declaration(args.body, files)
    errors.extend(validate_review_declaration(args.body, args.base_sha, args.head_sha))
    errors.extend(validate_size_declaration(args.body, len(files), additions, deletions))
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print("PR status and review declarations are consistent with the pull request")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
