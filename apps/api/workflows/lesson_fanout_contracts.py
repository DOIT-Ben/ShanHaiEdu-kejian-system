"""ORM-free published-topology contracts for lesson branch fanout."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from workflow.registry import RegisteredWorkflow


@dataclass(frozen=True, slots=True)
class LessonBranchFanoutPlan:
    branch_key: str
    entrypoint_node_keys: tuple[str, ...]
    entrypoint_dependencies: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class LessonFanoutTarget:
    lesson_unit_id: UUID
    branch_enabled: Mapping[str, bool]


@dataclass(frozen=True, slots=True)
class LessonFanoutResult:
    created_branch_count: int
    created_node_count: int
    archived_branch_count: int


def build_lesson_fanout_plan(
    registered: RegisteredWorkflow,
) -> tuple[LessonBranchFanoutPlan, ...]:
    """Derive lesson entrypoints only from the immutable published graph."""

    entrypoints: dict[str, list[tuple[str, tuple[str, ...]]]] = defaultdict(list)
    for node in registered.graph.nodes:
        if node.execution_scope != "lesson_unit" or not node.entrypoint:
            continue
        if node.branch_key is None:
            raise ValueError("published lesson entrypoint has no branch_key")
        entrypoints[node.branch_key].append((node.node_key, node.dependencies))
    return tuple(
        LessonBranchFanoutPlan(
            branch_key=branch_key,
            entrypoint_node_keys=tuple(node_key for node_key, _ in sorted(values)),
            entrypoint_dependencies=tuple(dependencies for _, dependencies in sorted(values)),
        )
        for branch_key, values in sorted(entrypoints.items())
    )


def validate_lesson_fanout_targets(
    targets: tuple[LessonFanoutTarget, ...],
    archived_lesson_unit_ids: tuple[UUID, ...],
    expected_branches: set[str],
) -> None:
    lesson_ids = [target.lesson_unit_id for target in targets]
    if len(lesson_ids) != len(set(lesson_ids)):
        raise ValueError("Lesson fanout targets are duplicated.")
    if len(archived_lesson_unit_ids) != len(set(archived_lesson_unit_ids)):
        raise ValueError("Lesson fanout archive targets are duplicated.")
    if set(lesson_ids) & set(archived_lesson_unit_ids):
        raise ValueError("Lesson fanout targets cannot be active and archived together.")
    if any(set(target.branch_enabled) != expected_branches for target in targets):
        raise ValueError("Lesson branch configuration does not match the fixed workflow.")
