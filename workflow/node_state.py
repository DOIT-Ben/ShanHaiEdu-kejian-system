"""NodeRun state machine independent from generation-job execution state."""

from __future__ import annotations

from enum import StrEnum


class NodeStatus(StrEnum):
    DISABLED = "disabled"
    NOT_READY = "not_ready"
    READY = "ready"
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    STALE = "stale"
    SKIPPED = "skipped"


class NodeStateError(ValueError):
    """Raised when a NodeRun attempts an undeclared state transition."""


ALLOWED_NODE_TRANSITIONS: dict[NodeStatus, frozenset[NodeStatus]] = {
    NodeStatus.DISABLED: frozenset(),
    NodeStatus.NOT_READY: frozenset({NodeStatus.READY, NodeStatus.DISABLED, NodeStatus.STALE}),
    NodeStatus.READY: frozenset(
        {
            NodeStatus.DRAFT,
            NodeStatus.QUEUED,
            NodeStatus.RUNNING,
            NodeStatus.PAUSED,
            NodeStatus.DISABLED,
            NodeStatus.SKIPPED,
        }
    ),
    NodeStatus.DRAFT: frozenset({NodeStatus.QUEUED, NodeStatus.REVIEW_REQUIRED, NodeStatus.STALE}),
    NodeStatus.QUEUED: frozenset(
        {NodeStatus.RUNNING, NodeStatus.CANCEL_REQUESTED, NodeStatus.FAILED}
    ),
    NodeStatus.RUNNING: frozenset(
        {
            NodeStatus.REVIEW_REQUIRED,
            NodeStatus.PARTIALLY_COMPLETED,
            NodeStatus.FAILED,
            NodeStatus.CANCEL_REQUESTED,
            NodeStatus.PAUSED,
        }
    ),
    NodeStatus.REVIEW_REQUIRED: frozenset(
        {NodeStatus.APPROVED, NodeStatus.DRAFT, NodeStatus.STALE}
    ),
    NodeStatus.APPROVED: frozenset({NodeStatus.STALE}),
    NodeStatus.PARTIALLY_COMPLETED: frozenset(
        {NodeStatus.QUEUED, NodeStatus.REVIEW_REQUIRED, NodeStatus.FAILED}
    ),
    NodeStatus.FAILED: frozenset({NodeStatus.QUEUED, NodeStatus.SKIPPED}),
    NodeStatus.PAUSED: frozenset({NodeStatus.READY, NodeStatus.CANCELLED}),
    NodeStatus.CANCEL_REQUESTED: frozenset({NodeStatus.CANCELLED, NodeStatus.FAILED}),
    NodeStatus.CANCELLED: frozenset(),
    NodeStatus.STALE: frozenset({NodeStatus.READY, NodeStatus.SKIPPED}),
    NodeStatus.SKIPPED: frozenset(),
}


def ensure_node_transition(current: NodeStatus, target: NodeStatus) -> None:
    if target not in ALLOWED_NODE_TRANSITIONS[current]:
        raise NodeStateError(f"invalid node transition: {current} -> {target}")
