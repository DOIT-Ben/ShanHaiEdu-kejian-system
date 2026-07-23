from __future__ import annotations

from pathlib import Path

from scripts.check_trusted_contract_workflows import (
    DUPLICATE_VIDEO_CHAIN,
    LEASE_WORKFLOW,
    validate_trusted_contract_workflows,
)

ROOT = Path(__file__).resolve().parents[2]


def test_trusted_contract_workflow_validation_passes() -> None:
    assert validate_trusted_contract_workflows(ROOT) == []


def test_untrusted_pull_request_workflow_is_rejected(tmp_path: Path) -> None:
    workflow = tmp_path / LEASE_WORKFLOW
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """name: development-lease
on:
  pull_request:
jobs:
  validate:
    steps:
      - uses: actions/checkout@v4
      - run: python scripts/check_development_lease.py
""",
        encoding="utf-8",
    )

    errors = validate_trusted_contract_workflows(tmp_path)

    assert any("untrusted pull_request context" in error for error in errors)


def test_untrusted_head_checkout_is_rejected(tmp_path: Path) -> None:
    workflow = tmp_path / LEASE_WORKFLOW
    workflow.parent.mkdir(parents=True)
    fetch_command = (
        "git fetch --no-tags origin "
        "+refs/pull/${{ github.event.pull_request.number }}/head:"
        "refs/remotes/origin/pr-head"
    )
    checker_command = (
        "python scripts/check_development_lease.py "
        "--base ${{ github.event.pull_request.base.sha }} "
        "--head ${{ github.event.pull_request.head.sha }}"
    )
    workflow.write_text(
        f"""name: development-lease
on:
  pull_request_target:
jobs:
  validate:
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{{{ github.event.pull_request.head.sha }}}}
          persist-credentials: false
      - run: {fetch_command}
      - run: {checker_command}
""",
        encoding="utf-8",
    )

    errors = validate_trusted_contract_workflows(tmp_path)

    assert any("checks out untrusted PR code" in error for error in errors)


def test_duplicate_video_chain_is_rejected(tmp_path: Path) -> None:
    source = ROOT / LEASE_WORKFLOW
    workflow = tmp_path / LEASE_WORKFLOW
    workflow.parent.mkdir(parents=True)
    workflow.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    duplicate = tmp_path / DUPLICATE_VIDEO_CHAIN
    duplicate.parent.mkdir(parents=True)
    duplicate.write_text("{}", encoding="utf-8")

    errors = validate_trusted_contract_workflows(tmp_path)

    assert any("must not duplicate" in error for error in errors)
