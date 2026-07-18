#!/usr/bin/env python3
"""Validate a pull request's status, review, and size declarations."""

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
MARKDOWN_H2_SECTION = re.compile(
    r"^##[ \t]+.*?(?=^##[ \t]+|\Z)",
    re.MULTILINE | re.DOTALL,
)
FIRST_REQUIRED_GOVERNANCE_PR = 93


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


def _review_field_values(section: str, label: str) -> list[str]:
    fields = re.finditer(
        rf"^\s*{re.escape(label)}\s*[\uFF1A:]\s*(?P<value>.*?)\s*$",
        section,
        re.MULTILINE,
    )
    return [field.group("value").strip().strip("`").strip() for field in fields]


def validate_review_declaration(
    body: str,
    base_sha: str,
    head_sha: str,
    *,
    required: bool = False,
    is_draft: bool = True,
) -> list[str]:
    if REVIEW_MARKER.search(body) is None:
        if required:
            return ["PR must contain exactly one subagent review section"]
        return []

    review_sections = [
        match.group()
        for match in MARKDOWN_H2_SECTION.finditer(body)
        if REVIEW_MARKER.search(match.group()) is not None
    ]
    if len(review_sections) != 1:
        return ["PR must contain exactly one subagent review section"]
    section = review_sections[0]

    choices = [
        match.group("choice")
        for match in REVIEW_DECLARATION.finditer(section)
        if match.group("checked").lower() == "x"
    ]
    if len(choices) != 1:
        return ["PR must select exactly one subagent review declaration"]

    errors: list[str] = []
    base_fields = _review_field_values(section, "Base SHA")
    head_fields = _review_field_values(section, "Head SHA")
    if len(base_fields) != 1:
        errors.append("subagent review section must contain exactly one Base SHA field")
    if len(head_fields) != 1:
        errors.append("subagent review section must contain exactly one Head SHA field")
    if errors:
        return errors

    if choices[0] == "subagent-review-pending":
        if not is_draft:
            return ["non-draft PR must select subagent-review-approved"]
        return []

    declared_base = base_fields[0]
    declared_head = head_fields[0]
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
    binary_file_count: int = 0,
    *,
    required: bool = False,
) -> list[str]:
    if SIZE_MARKER.search(body) is None:
        if required:
            return ["PR must select exactly one pull request size declaration"]
        return []

    choices = [
        match.group("choice")
        for match in SIZE_DECLARATION.finditer(body)
        if match.group("checked").lower() == "x"
    ]
    if len(choices) != 1:
        return ["PR must select exactly one pull request size declaration"]

    exceeds_raw_trigger = (
        changed_file_count > 20 or additions - deletions > 800 or binary_file_count > 0
    )
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


def parse_numstat(output: str) -> tuple[int, int, int]:
    additions = 0
    deletions = 0
    binary_file_count = 0
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            binary_file_count += 1
            continue
        added, deleted, _path = parts
        if added.isdigit() and deleted.isdigit():
            additions += int(added)
            deletions += int(deleted)
        else:
            binary_file_count += 1
    return additions, deletions, binary_file_count


def changed_line_counts(base_sha: str, head_sha: str) -> tuple[int, int, int]:
    result = subprocess.run(
        ["git", "diff", "--numstat", f"{base_sha}...{head_sha}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_numstat(result.stdout)


def parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--is-draft", required=True, type=parse_bool)
    args = parser.parse_args()

    files = changed_files(args.base_sha, args.head_sha)
    additions, deletions, binary_file_count = changed_line_counts(args.base_sha, args.head_sha)
    declarations_required = args.pr_number >= FIRST_REQUIRED_GOVERNANCE_PR
    errors = validate_status_declaration(args.body, files)
    errors.extend(
        validate_review_declaration(
            args.body,
            args.base_sha,
            args.head_sha,
            required=declarations_required,
            is_draft=args.is_draft,
        )
    )
    errors.extend(
        validate_size_declaration(
            args.body,
            len(files),
            additions,
            deletions,
            binary_file_count,
            required=declarations_required,
        )
    )
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print("PR declarations are consistent with the pull request")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
