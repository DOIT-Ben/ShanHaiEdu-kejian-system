"""Workflow run creation, node transitions, and immutable input capture."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.projects.policy_service import AutomationPolicyService
from apps.api.workflows.models import (
    NodeInputSnapshot,
    NodeRun,
    WorkflowDefinitionVersion,
    WorkflowRun,
)
from apps.api.workflows.repository import WorkflowRuntimeRepository
from workflow.node_state import NodeStateError, NodeStatus, ensure_node_transition
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY, RegisteredWorkflow


class WorkflowRuntimeError(ValueError):
    """Raised when a workflow runtime invariant is violated."""


class WorkflowRuntimeService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = WorkflowRuntimeRepository(session, actor)

    def start_project_run(self, project_id: UUID) -> WorkflowRun:
        project = ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.EDIT,
            for_update=True,
        )
        if project.status == "archived":
            raise WorkflowRuntimeError("archived projects cannot start workflow runs")
        if self._repository.active_for_project(project_id, for_update=True) is not None:
            raise WorkflowRuntimeError("project already has an active workflow run")
        self._load_registered_workflow(project.workflow_definition_version_id)
        policy_snapshot = AutomationPolicyService(self._session, self._actor).snapshot(project.id)
        if policy_snapshot["workflow_definition_version_id"] != str(
            project.workflow_definition_version_id
        ):
            raise WorkflowRuntimeError("automation policy uses a different workflow definition")
        run = WorkflowRun(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=project.id,
            workflow_definition_version_id=project.workflow_definition_version_id,
            content_release_id=project.content_release_id,
            automation_policy_snapshot_json=policy_snapshot,
            run_no=self._repository.next_run_no(project.id),
            status="active",
            current_event_seq=0,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(run)
        self._session.flush()
        return run

    def create_project_node_run(
        self,
        workflow_run_id: UUID,
        *,
        node_key: str,
        status: NodeStatus,
    ) -> NodeRun:
        run = self._require_run(workflow_run_id)
        ProjectAccessService(self._session, self._actor).require(
            run.project_id,
            ProjectAction.EDIT,
        )
        registered = self._load_registered_workflow(run.workflow_definition_version_id)
        if node_key not in registered.topological_order:
            raise WorkflowRuntimeError("node_key is not declared by the workflow definition")
        if status not in {NodeStatus.DISABLED, NodeStatus.NOT_READY, NodeStatus.READY}:
            raise WorkflowRuntimeError("node run initial status is invalid")
        node = NodeRun(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            workflow_run_id=run.id,
            branch_run_id=None,
            node_key=node_key,
            run_no=self._repository.next_node_run_no(run.id, None, node_key),
            status=status.value,
            trigger_type="manual",
            automation_policy_snapshot_json=run.automation_policy_snapshot_json,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(node)
        self._session.flush()
        return node

    def add_input_snapshot(
        self,
        node_run_id: UUID,
        *,
        input_key: str,
        source_type: str,
        source_id: UUID,
        source_version_id: UUID | None,
        content_hash: str,
        snapshot: dict[str, object],
    ) -> NodeInputSnapshot:
        node = self._require_node(node_run_id, for_update=True)
        run = self._require_run(node.workflow_run_id)
        ProjectAccessService(self._session, self._actor).require(
            run.project_id,
            ProjectAction.EDIT,
        )
        if NodeStatus(node.status) not in {
            NodeStatus.NOT_READY,
            NodeStatus.READY,
            NodeStatus.DRAFT,
        }:
            raise WorkflowRuntimeError("node inputs are frozen after execution starts")
        record = NodeInputSnapshot(
            id=new_uuid7(),
            node_run_id=node.id,
            input_key=input_key,
            source_type=source_type,
            source_id=source_id,
            source_version_id=source_version_id,
            content_hash=content_hash,
            snapshot_json=snapshot,
            created_by=self._actor.principal_id,
        )
        self._session.add(record)
        self._session.flush()
        return record

    def transition_node(self, node_run_id: UUID, target: NodeStatus) -> NodeRun:
        node = self._require_node(node_run_id, for_update=True)
        run = self._require_run(node.workflow_run_id)
        ProjectAccessService(self._session, self._actor).require(
            run.project_id,
            ProjectAction.EDIT,
        )
        try:
            ensure_node_transition(NodeStatus(node.status), target)
        except NodeStateError as exc:
            raise WorkflowRuntimeError(str(exc)) from exc
        if target in {
            NodeStatus.QUEUED,
            NodeStatus.RUNNING,
            NodeStatus.CANCEL_REQUESTED,
        }:
            active = self._repository.active_node(
                node.workflow_run_id,
                node.branch_run_id,
                node.node_key,
            )
            if active is not None and active.id != node.id:
                raise WorkflowRuntimeError("node already has an active execution")
        now = utc_now()
        node.status = target.value
        node.updated_by = self._actor.principal_id
        node.updated_at = now
        node.lock_version += 1
        if target == NodeStatus.RUNNING and node.started_at is None:
            node.started_at = now
        if target in {NodeStatus.CANCELLED, NodeStatus.SKIPPED}:
            node.finished_at = now
        self._session.flush()
        return node

    def _require_run(self, run_id: UUID) -> WorkflowRun:
        run = self._repository.get_run(run_id)
        if run is None:
            raise WorkflowRuntimeError("workflow run was not found")
        return run

    def _require_node(self, node_id: UUID, *, for_update: bool = False) -> NodeRun:
        node = self._repository.get_node(node_id, for_update=for_update)
        if node is None:
            raise WorkflowRuntimeError("node run was not found")
        return node

    def _load_registered_workflow(self, version_id: UUID) -> RegisteredWorkflow:
        definition = self._session.get(WorkflowDefinitionVersion, version_id)
        if definition is None or definition.status != "published":
            raise WorkflowRuntimeError("project workflow definition is not published")
        return BUILTIN_WORKFLOW_REGISTRY.load(definition.graph_json)
