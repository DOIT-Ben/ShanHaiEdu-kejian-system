#!/usr/bin/env python3
"""Validate a pull request's CURRENT_STATUS freshness declaration."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

DECLARATION = re.compile(
    r"^-\s*\[[xX]\]\s*`(?P<choice>status-update-(?:required|not-required))`",
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


def changed_files(base_sha: str, head_sha: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--body", required=True)
    args = parser.parse_args()

    errors = validate_status_declaration(
        args.body,
        changed_files(args.base_sha, args.head_sha),
    )
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print("CURRENT_STATUS freshness declaration is consistent with the PR diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
