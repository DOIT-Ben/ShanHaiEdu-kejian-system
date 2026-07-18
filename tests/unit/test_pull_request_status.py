from __future__ import annotations

from scripts.check_pull_request_status import (
    validate_review_declaration,
    validate_status_declaration,
)

REQUIRED = "- [x] `status-update-required`: status changed"
NOT_REQUIRED = "- [x] `status-update-not-required`: status did not change"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
PENDING = "- [x] `subagent-review-pending`: review pending"
APPROVED = "- [x] `subagent-review-approved`: review approved"
PENDING_UNCHECKED = "- [ ] `subagent-review-pending`: review pending"
APPROVED_UNCHECKED = "- [ ] `subagent-review-approved`: review approved"


def test_status_update_declaration_requires_current_status_change() -> None:
    errors = validate_status_declaration(REQUIRED, {"apps/api/main.py"})

    assert errors == ["PR declares status-update-required but does not change CURRENT_STATUS.md"]


def test_status_update_declaration_accepts_current_status_change() -> None:
    errors = validate_status_declaration(REQUIRED, {"CURRENT_STATUS.md"})

    assert errors == []


def test_no_status_update_declaration_rejects_current_status_change() -> None:
    errors = validate_status_declaration(NOT_REQUIRED, {"CURRENT_STATUS.md"})

    assert errors == ["PR changes CURRENT_STATUS.md but declares status-update-not-required"]


def test_status_declaration_requires_exactly_one_choice() -> None:
    assert validate_status_declaration("", set()) == [
        "PR must select exactly one CURRENT_STATUS freshness declaration"
    ]
    assert validate_status_declaration(f"{REQUIRED}\n{NOT_REQUIRED}", set()) == [
        "PR must select exactly one CURRENT_STATUS freshness declaration"
    ]


def test_review_declaration_keeps_legacy_pr_body_compatible() -> None:
    assert validate_review_declaration("legacy PR body", BASE_SHA, HEAD_SHA) == []


def test_review_declaration_requires_exactly_one_choice_when_present() -> None:
    assert validate_review_declaration(
        f"{PENDING_UNCHECKED}\n{APPROVED_UNCHECKED}", BASE_SHA, HEAD_SHA
    ) == ["PR must select exactly one subagent review declaration"]
    assert validate_review_declaration(f"{PENDING}\n{APPROVED}", BASE_SHA, HEAD_SHA) == [
        "PR must select exactly one subagent review declaration"
    ]


def test_pending_review_declaration_allows_empty_sha_fields() -> None:
    body = f"{PENDING}\n{APPROVED_UNCHECKED}\n\nBase SHA：\n\nHead SHA："

    assert validate_review_declaration(body, BASE_SHA, HEAD_SHA) == []


def test_approved_review_declaration_requires_full_sha_fields() -> None:
    body = (
        f"{PENDING_UNCHECKED}\n{APPROVED}\n\n"
        "Base SHA：1234567\n\n"
        "Head SHA："
    )

    assert validate_review_declaration(body, BASE_SHA, HEAD_SHA) == [
        "subagent-review-approved requires a full 40-character Base SHA",
        "subagent-review-approved requires a full 40-character Head SHA",
    ]


def test_approved_review_declaration_requires_matching_sha_fields() -> None:
    body = (
        f"{PENDING_UNCHECKED}\n{APPROVED}\n\n"
        f"Base SHA：{'3' * 40}\n\n"
        f"Head SHA：{'4' * 40}"
    )

    assert validate_review_declaration(body, BASE_SHA, HEAD_SHA) == [
        "subagent review Base SHA does not match the pull request base SHA",
        "subagent review Head SHA does not match the pull request head SHA",
    ]


def test_approved_review_declaration_accepts_exact_sha_fields() -> None:
    body = (
        f"{PENDING_UNCHECKED}\n{APPROVED}\n\n"
        f"Base SHA：`{BASE_SHA}`\n\n"
        f"Head SHA：`{HEAD_SHA}`"
    )

    assert validate_review_declaration(body, BASE_SHA, HEAD_SHA) == []
