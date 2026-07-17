from __future__ import annotations

from scripts.check_pull_request_status import validate_status_declaration

REQUIRED = "- [x] `status-update-required`: status changed"
NOT_REQUIRED = "- [x] `status-update-not-required`: status did not change"


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
