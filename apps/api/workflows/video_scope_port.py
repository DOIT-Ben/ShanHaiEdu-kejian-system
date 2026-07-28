"""Workflow-owned runtime facts and mutations for video generation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.workflows.models import (
    BranchRun,
    NodeRun,
    WorkflowDefinitionVersion,
    WorkflowRun,
)
from apps.api.workflows.repository import WorkflowRuntimeRepository

VIDEO_NODE_KEY = "video.shots.generate"


@dataclass(frozen=True, slots=True)
class VideoWorkflowScope:
    workflow_run_id: UUID
    branch_run_id: UUID
    automation_policy_snapshot: dict[str, Any]


class VideoWorkflowPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def active_scope(
        self, project_id: UUID, lesson_id: UUID, *, for_update: bool = False
    ) -> VideoWorkflowScope | None:
        statement = (
            select(WorkflowRun, BranchRun, WorkflowDefinitionVersion)
            .join(BranchRun, BranchRun.workflow_run_id == WorkflowRun.id)
            .join(
                WorkflowDefinitionVersion,
                WorkflowDefinitionVersion.id == WorkflowRun.workflow_definition_version_id,
            )
            .where(
                WorkflowRun.project_id == project_id,
                WorkflowRun.organization_id == self._actor.organization_id,
                WorkflowRun.status == "active",
                WorkflowRun.deleted_at.is_(None),
                WorkflowDefinitionVersion.status == "published",
                BranchRun.lesson_unit_id == lesson_id,
                BranchRun.branch_key == "video",
                BranchRun.status == "active",
                BranchRun.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=(WorkflowRun, BranchRun))
        row = self._session.execute(statement).one_or_none()
        if row is None or not _supports_golden_slice(row[2].graph_json):
            return None
        return VideoWorkflowScope(
            workflow_run_id=row[0].id,
            branch_run_id=row[1].id,
            automation_policy_snapshot=dict(row[0].automation_policy_snapshot_json),
        )

    def create_queued_node(self, scope: VideoWorkflowScope) -> UUID:
        run_no = WorkflowRuntimeRepository(self._session, self._actor).next_node_run_no(
            scope.workflow_run_id, scope.branch_run_id, VIDEO_NODE_KEY
        )
        node = NodeRun(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            workflow_run_id=scope.workflow_run_id,
            branch_run_id=scope.branch_run_id,
            node_key=VIDEO_NODE_KEY,
            run_no=run_no,
            status="queued",
            trigger_type="manual",
            automation_policy_snapshot_json=scope.automation_policy_snapshot,
            started_at=None,
            finished_at=None,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(node)
        self._session.flush()
        return node.id

    def set_last_error_if_active(self, node_run_id: UUID, error_code: str) -> bool:
        node = self._session.get(NodeRun, node_run_id, with_for_update=True)
        if node is None or node.status not in {"queued", "running"}:
            return False
        node.last_error_code = error_code
        return True

    def is_active(self, node_run_id: UUID) -> bool:
        node = self._session.get(NodeRun, node_run_id, with_for_update=True)
        return node is not None and node.status in {"queued", "running"}


def _supports_golden_slice(graph: dict[str, Any]) -> bool:
    raw_nodes = graph.get("nodes")
    if not isinstance(raw_nodes, list):
        return False
    node: Mapping[str, object] | None = None
    for raw_node in cast(list[object], raw_nodes):
        if not isinstance(raw_node, Mapping):
            continue
        candidate = cast(Mapping[str, object], raw_node)
        if candidate.get("node_key") == VIDEO_NODE_KEY:
            node = candidate
            break
    if node is None:
        return False
    raw_reference_policy = node.get("reference_asset_policy")
    if not isinstance(raw_reference_policy, Mapping):
        return False
    reference_policy = cast(Mapping[str, object], raw_reference_policy)
    return (
        node.get("entrypoint") is True
        and node.get("dependencies") == []
        and node.get("input_contract_refs") == ["selection:intro", "asset:shot_keyframe"]
        and node.get("context_policy")
        == {
            "mode": "declared",
            "allowed_sources": ["intro_selection.snapshot"],
            "forbidden_sources": [
                "lesson_plan.approved_version",
                "material.approved_parse",
                "ppt_outline.approved_version",
                "video_fine_storyboard.approved_version",
            ],
        }
        and reference_policy.get("roles")
        == [
            {
                "role_key": "shot_keyframe",
                "requirement": "required",
                "media_types": ["image"],
                "min_items": 1,
                "max_items": 1,
                "order_mode": "stable_by_role_then_version",
                "allowed_sources": ["asset_slot_current"],
                "provider_exposure": ["signed_url", "provider_file_id", "inline_bytes"],
            }
        ]
    )
