from __future__ import annotations

import pytest

from apps.api.assets.domain import ParseInvariantError, ParseStatus, ensure_parse_transition


@pytest.mark.parametrize(
    ("current", "target"),
    (
        (ParseStatus.PENDING, ParseStatus.RUNNING),
        (ParseStatus.RUNNING, ParseStatus.SUCCEEDED),
        (ParseStatus.RUNNING, ParseStatus.FAILED),
    ),
)
def test_parse_version_allows_only_forward_execution_transitions(
    current: ParseStatus,
    target: ParseStatus,
) -> None:
    ensure_parse_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    (
        (ParseStatus.PENDING, ParseStatus.SUCCEEDED),
        (ParseStatus.FAILED, ParseStatus.RUNNING),
        (ParseStatus.SUCCEEDED, ParseStatus.RUNNING),
        (ParseStatus.SUCCEEDED, ParseStatus.FAILED),
    ),
)
def test_terminal_parse_versions_are_immutable_and_retry_requires_a_new_version(
    current: ParseStatus,
    target: ParseStatus,
) -> None:
    with pytest.raises(ParseInvariantError):
        ensure_parse_transition(current, target)
