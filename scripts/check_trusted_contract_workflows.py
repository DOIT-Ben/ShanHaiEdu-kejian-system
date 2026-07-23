#!/usr/bin/env python3
"""Validate that contract governance workflows cannot execute untrusted PR code."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEASE_WORKFLOW = Path(".github/workflows/development-lease.yml")
LEASE_CHECKER = Path("scripts/check_development_lease.py")
DUPLICATE_VIDEO_CHAIN = Path("contracts/fixtures/parallel-inputs/video/complete-chain.json")


def validate_trusted_contract_workflows(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    workflow_path = root / LEASE_WORKFLOW
    if not workflow_path.is_file():
        return [f"missing trusted lease workflow: {LEASE_WORKFLOW}"]

    text = workflow_path.read_text(encoding="utf-8")
    required_fragments = {
        "pull_request_target trigger": "pull_request_target:",
        "trusted base checkout": "ref: ${{ github.event.pull_request.base.sha }}",
        "credentials disabled": "persist-credentials: false",
        "PR objects fetched without checkout": (
            "+refs/pull/${{ github.event.pull_request.number }}/head:refs/remotes/origin/pr-head"
        ),
        "trusted checker invocation": "python scripts/check_development_lease.py",
        "exact base argument": "--base ${{ github.event.pull_request.base.sha }}",
        "exact head argument": "--head ${{ github.event.pull_request.head.sha }}",
    }
    for label, fragment in required_fragments.items():
        if fragment not in text:
            errors.append(f"development lease workflow lacks {label}")

    if re.search(r"(?m)^\s{2}pull_request:\s*$", text):
        errors.append(
            "development lease workflow must not run from the untrusted pull_request context"
        )
    if text.count("uses: actions/checkout@") != 1:
        errors.append("development lease workflow must perform exactly one trusted checkout")
    forbidden_checkout_refs = (
        "ref: ${{ github.event.pull_request.head.sha }}",
        "ref: refs/pull/",
        "ref: ${{ github.event.pull_request.head.ref }}",
    )
    for fragment in forbidden_checkout_refs:
        if fragment in text:
            errors.append(f"development lease workflow checks out untrusted PR code: {fragment}")

    checker_path = root / LEASE_CHECKER
    if not checker_path.is_file():
        errors.append(f"missing trusted lease checker: {LEASE_CHECKER}")
    else:
        checker_text = checker_path.read_text(encoding="utf-8")
        checker_fragments = {
            "NUL-delimited name-status parsing": '"--name-status"',
            "NUL path delimiter": '"-z"',
            "rename detection": '"--find-renames"',
            "copy detection": '"--find-copies"',
            "type-change coverage": '"--diff-filter=ACMRTD"',
        }
        for label, fragment in checker_fragments.items():
            if fragment not in checker_text:
                errors.append(f"development lease checker lacks {label}")
        if '"--name-only"' in checker_text:
            errors.append("development lease checker must not use rename-unsafe --name-only output")

    if (root / DUPLICATE_VIDEO_CHAIN).exists():
        errors.append(
            "parallel video fixtures must not duplicate the canonical video node sequence; "
            "use contracts/full-chain-freeze.json"
        )
    return errors


def main() -> int:
    errors = validate_trusted_contract_workflows()
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("trusted contract workflow checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
