from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/repository-governance.yml"


def test_pull_request_declaration_checks_rerun_for_body_and_draft_changes() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    for event in ("edited", "ready_for_review", "converted_to_draft"):
        assert f"      - {event}" in text


def test_pull_request_declaration_check_receives_pr_identity_and_draft_state() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert '--pr-number "${{ github.event.pull_request.number }}"' in text
    assert '--is-draft "${{ github.event.pull_request.draft }}"' in text
