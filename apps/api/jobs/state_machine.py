"""Generation-job state transition rules."""

from __future__ import annotations

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "created": frozenset({"queued", "cancel_requested"}),
    "queued": frozenset({"running", "cancel_requested"}),
    "running": frozenset({"succeeded", "failed", "cancel_requested"}),
    "cancel_requested": frozenset({"cancelled"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class InvalidJobTransition(ValueError):
    pass


def require_transition(current: str, target: str) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidJobTransition(f"generation job cannot transition from {current} to {target}")
