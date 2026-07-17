from __future__ import annotations

import pytest

from workflow.node_state import NodeStateError, NodeStatus, ensure_node_transition


@pytest.mark.parametrize(
    ("current", "target"),
    (
        (NodeStatus.NOT_READY, NodeStatus.READY),
        (NodeStatus.READY, NodeStatus.QUEUED),
        (NodeStatus.QUEUED, NodeStatus.RUNNING),
        (NodeStatus.RUNNING, NodeStatus.REVIEW_REQUIRED),
        (NodeStatus.REVIEW_REQUIRED, NodeStatus.APPROVED),
        (NodeStatus.APPROVED, NodeStatus.STALE),
    ),
)
def test_node_state_allows_declared_workflow_progression(
    current: NodeStatus,
    target: NodeStatus,
) -> None:
    ensure_node_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    (
        (NodeStatus.DISABLED, NodeStatus.RUNNING),
        (NodeStatus.NOT_READY, NodeStatus.APPROVED),
        (NodeStatus.QUEUED, NodeStatus.APPROVED),
        (NodeStatus.APPROVED, NodeStatus.RUNNING),
        (NodeStatus.SKIPPED, NodeStatus.APPROVED),
    ),
)
def test_node_state_rejects_generation_job_shortcuts(
    current: NodeStatus,
    target: NodeStatus,
) -> None:
    with pytest.raises(NodeStateError):
        ensure_node_transition(current, target)
