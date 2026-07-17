"""File asset and material parse version business rules."""

from __future__ import annotations

from enum import StrEnum


class ParseStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ParseInvariantError(ValueError):
    """Raised when a parse version would violate immutable execution history."""


ALLOWED_PARSE_TRANSITIONS: dict[ParseStatus, frozenset[ParseStatus]] = {
    ParseStatus.PENDING: frozenset({ParseStatus.RUNNING}),
    ParseStatus.RUNNING: frozenset({ParseStatus.SUCCEEDED, ParseStatus.FAILED}),
    ParseStatus.SUCCEEDED: frozenset(),
    ParseStatus.FAILED: frozenset(),
}


def ensure_parse_transition(current: ParseStatus, target: ParseStatus) -> None:
    if target not in ALLOWED_PARSE_TRANSITIONS[current]:
        raise ParseInvariantError(f"invalid material parse transition: {current} -> {target}")
