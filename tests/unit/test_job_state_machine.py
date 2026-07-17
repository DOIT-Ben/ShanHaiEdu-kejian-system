from __future__ import annotations

import pytest

from apps.api.jobs.state_machine import InvalidJobTransition, require_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("queued", "running"),
        ("queued", "cancel_requested"),
        ("running", "succeeded"),
        ("running", "failed"),
        ("running", "cancel_requested"),
        ("cancel_requested", "cancelled"),
    ],
)
def test_supported_job_transitions(current: str, target: str) -> None:
    require_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("succeeded", "running"),
        ("cancelled", "queued"),
        ("failed", "succeeded"),
        ("queued", "succeeded"),
    ],
)
def test_invalid_job_transitions_are_rejected(current: str, target: str) -> None:
    with pytest.raises(InvalidJobTransition):
        require_transition(current, target)
