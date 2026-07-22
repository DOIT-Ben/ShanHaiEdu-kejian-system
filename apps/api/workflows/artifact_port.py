"""Workflow-owned staging for lesson-scoped generated Artifact versions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.workflows.artifact_input_selection import (
    ARTIFACT_INPUT_SELECTION_KEY,
    artifact_input_selection_hash,
    artifact_input_selection_payload,
)
from apps.api.workflows.models import (
    BranchRun,
    NodeInputSnapshot,
    NodeRun,
    WorkflowDefinitionVersion,
    WorkflowRun,
)
from apps.api.workflows.repository import WorkflowRuntimeRepository
from apps.api.workflows.service import WorkflowRuntimeService
from workflow.definition import WorkflowOutputDefinitionBinding
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

_ACTIVE_STATUSES = frozenset({NodeStatus.QUEUED, NodeStatus.RUNNING, NodeStatus.CANCEL_REQUESTED})


@dataclass(frozen=True, slots=True)
class ArtifactInputSnapshot:
    input_key: str
    source_type: str
    source_id: UUID
    source_version_id: UUID
    content_hash: str
    content: dict[str, object]


@dataclass(frozen=True, slots=True)
class ArtifactRunScope:
    workflow_run_id: UUID
    branch_run_id: UUID
    content_release_id: UUID
    workflow_definition_version_id: UUID


class ArtifactWorkflowPort:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        error_code: str = "ARTIFACT_WORKFLOW_RUNTIME_INVALID",
    ) -> None:
        self._session = session
        self._actor = actor
        self._error_code = error_code
        self._repository = WorkflowRuntimeRepository(session, actor)

    def output_binding(
        self,
        workflow_definition_version_id: UUID,
        content_definition_key: str,
    ) -> WorkflowOutputDefinitionBinding:
        workflow = self._session.get(WorkflowDefinitionVersion, workflow_definition_version_id)
        if workflow is None or workflow.status != "published":
            raise self._invalid("The fixed workflow definition is unavailable.")
        output = BUILTIN_WORKFLOW_REGISTRY.load(workflow.graph_json).output_definition_index.get(
            content_definition_key
        )
        if output is None or output.execution_scope != "lesson_unit":
            raise self._invalid("The lesson Artifact output binding is unavailable.")
        return output

    def require_lesson_scope(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
        branch_key: str,
    ) -> ArtifactRunScope:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.GENERATE,
        )
        row = self._session.execute(
            select(BranchRun, WorkflowRun)
            .join(WorkflowRun, WorkflowRun.id == BranchRun.workflow_run_id)
            .where(
                WorkflowRun.organization_id == self._actor.organization_id,
                WorkflowRun.project_id == project_id,
                WorkflowRun.status == "active",
                WorkflowRun.deleted_at.is_(None),
                BranchRun.lesson_unit_id == lesson_unit_id,
                BranchRun.branch_key == branch_key,
                BranchRun.status == "active",
                BranchRun.deleted_at.is_(None),
            )
            .with_for_update(of=BranchRun)
        ).one_or_none()
        if row is None:
            raise self._invalid("The active lesson Artifact branch is unavailable.")
        branch, run = row
        return ArtifactRunScope(
            workflow_run_id=run.id,
            branch_run_id=branch.id,
            content_release_id=run.content_release_id,
            workflow_definition_version_id=run.workflow_definition_version_id,
        )

    def stage_generation(
        self,
        scope: ArtifactRunScope,
        producer_node_key: str,
        *,
        selected_artifact_versions: Mapping[str, UUID],
    ) -> UUID:
        latest = self._session.scalar(
            select(NodeRun)
            .where(
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.workflow_run_id == scope.workflow_run_id,
                NodeRun.branch_run_id == scope.branch_run_id,
                NodeRun.node_key == producer_node_key,
                NodeRun.deleted_at.is_(None),
            )
            .order_by(NodeRun.run_no.desc())
            .limit(1)
            .with_for_update(of=NodeRun)
        )
        if latest is None:
            raise self._invalid("The published lesson Artifact entrypoint is unavailable.")
        status = NodeStatus(latest.status)
        if status in _ACTIVE_STATUSES:
            raise self._invalid("The lesson Artifact generation is already active.")
        if status is NodeStatus.READY:
            node = latest
        else:
            node = WorkflowRuntimeService(self._session, self._actor).create_branch_node_run(
                scope.workflow_run_id,
                scope.branch_run_id,
                node_key=producer_node_key,
                status=NodeStatus.READY,
            )
        self._freeze_artifact_selection(node.id, scope, selected_artifact_versions)
        return node.id

    def require_source_scope(
        self,
        *,
        source_node_run_id: UUID,
        source_artifact_version_id: UUID,
        expected_producer_node_key: str,
        project_id: UUID,
        lesson_unit_id: UUID,
        content_release_id: UUID,
        workflow_definition_version_id: UUID,
    ) -> ArtifactRunScope:
        row = self._session.execute(
            select(NodeRun, BranchRun, WorkflowRun)
            .join(BranchRun, BranchRun.id == NodeRun.branch_run_id)
            .join(WorkflowRun, WorkflowRun.id == NodeRun.workflow_run_id)
            .where(
                NodeRun.id == source_node_run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.node_key == expected_producer_node_key,
                NodeRun.active_artifact_version_id == source_artifact_version_id,
                NodeRun.deleted_at.is_(None),
                BranchRun.lesson_unit_id == lesson_unit_id,
                BranchRun.status == "active",
                BranchRun.deleted_at.is_(None),
                WorkflowRun.project_id == project_id,
                WorkflowRun.content_release_id == content_release_id,
                WorkflowRun.workflow_definition_version_id == workflow_definition_version_id,
                WorkflowRun.status == "active",
            )
            .with_for_update(of=NodeRun)
        ).one_or_none()
        if row is None:
            raise self._invalid("The generated Artifact is outside its fixed lesson branch.")
        _node, branch, run = row
        return ArtifactRunScope(
            run.id,
            branch.id,
            run.content_release_id,
            run.workflow_definition_version_id,
        )

    def stage_quality(
        self,
        scope: ArtifactRunScope,
        validate_node_key: str,
        *,
        source: ArtifactInputSnapshot,
        supporting: tuple[ArtifactInputSnapshot, ...],
    ) -> UUID:
        existing = self._node_for_source(scope.branch_run_id, validate_node_key, source)
        runtime = WorkflowRuntimeService(self._session, self._actor)
        node = existing or runtime.create_branch_node_run(
            scope.workflow_run_id,
            scope.branch_run_id,
            node_key=validate_node_key,
            status=NodeStatus.NOT_READY,
        )
        replayed = tuple(
            self._ensure_snapshot(node.id, snapshot, runtime) for snapshot in (source, *supporting)
        )
        if NodeStatus(node.status) is NodeStatus.NOT_READY:
            runtime.transition_node(node.id, NodeStatus.READY)
        elif not all(replayed):
            raise self._invalid("The validate node cannot accept different frozen inputs.")
        return node.id

    def open_gate(
        self,
        scope: ArtifactRunScope,
        gate_node_key: str,
        *,
        source: ArtifactInputSnapshot,
        report: ArtifactInputSnapshot,
    ) -> UUID:
        existing = self._node_for_source(scope.branch_run_id, gate_node_key, source)
        runtime = WorkflowRuntimeService(self._session, self._actor)
        node = existing or runtime.create_branch_node_run(
            scope.workflow_run_id,
            scope.branch_run_id,
            node_key=gate_node_key,
            status=NodeStatus.NOT_READY,
        )
        replayed = (
            self._ensure_snapshot(node.id, source, runtime),
            self._ensure_snapshot(node.id, report, runtime),
        )
        status = NodeStatus(node.status)
        if status is NodeStatus.NOT_READY:
            runtime.transition_node(node.id, NodeStatus.READY)
            runtime.transition_node(node.id, NodeStatus.DRAFT)
            runtime.transition_node(node.id, NodeStatus.REVIEW_REQUIRED)
        elif status is not NodeStatus.REVIEW_REQUIRED or not all(replayed):
            raise self._invalid("The approval gate cannot accept different frozen inputs.")
        return node.id

    def _freeze_artifact_selection(
        self,
        node_run_id: UUID,
        scope: ArtifactRunScope,
        selection: Mapping[str, UUID],
    ) -> None:
        payload = artifact_input_selection_payload(selection)
        content_hash = artifact_input_selection_hash(payload)
        existing = self._session.scalar(
            select(NodeInputSnapshot)
            .where(
                NodeInputSnapshot.node_run_id == node_run_id,
                NodeInputSnapshot.input_key == ARTIFACT_INPUT_SELECTION_KEY,
            )
            .with_for_update(of=NodeInputSnapshot)
        )
        if existing is not None:
            if existing.content_hash == content_hash and existing.snapshot_json == payload:
                return
            raise self._invalid("The generation node already has another exact input selection.")
        self._session.add(
            NodeInputSnapshot(
                id=new_uuid7(),
                node_run_id=node_run_id,
                input_key=ARTIFACT_INPUT_SELECTION_KEY,
                source_type="workflow_definition",
                source_id=scope.workflow_run_id,
                source_version_id=scope.workflow_definition_version_id,
                content_hash=content_hash,
                snapshot_json=payload,
                created_by=self._actor.principal_id,
            )
        )
        self._session.flush()

    def _node_for_source(
        self,
        branch_run_id: UUID,
        node_key: str,
        source: ArtifactInputSnapshot,
    ) -> NodeRun | None:
        return self._session.scalar(
            select(NodeRun)
            .join(NodeInputSnapshot, NodeInputSnapshot.node_run_id == NodeRun.id)
            .where(
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.branch_run_id == branch_run_id,
                NodeRun.node_key == node_key,
                NodeRun.deleted_at.is_(None),
                NodeInputSnapshot.input_key == source.input_key,
                NodeInputSnapshot.source_version_id == source.source_version_id,
                NodeInputSnapshot.content_hash == source.content_hash,
            )
            .order_by(NodeRun.run_no.desc())
            .limit(1)
            .with_for_update(of=NodeRun)
        )

    def _ensure_snapshot(
        self,
        node_run_id: UUID,
        expected: ArtifactInputSnapshot,
        runtime: WorkflowRuntimeService,
    ) -> bool:
        existing = self._session.scalar(
            select(NodeInputSnapshot)
            .where(
                NodeInputSnapshot.node_run_id == node_run_id,
                NodeInputSnapshot.input_key == expected.input_key,
            )
            .with_for_update(of=NodeInputSnapshot)
        )
        if existing is None:
            runtime.add_input_snapshot(
                node_run_id,
                input_key=expected.input_key,
                source_type=expected.source_type,
                source_id=expected.source_id,
                source_version_id=expected.source_version_id,
                content_hash=expected.content_hash,
                snapshot=expected.content,
            )
            return False
        if (
            existing.source_type != expected.source_type
            or existing.source_id != expected.source_id
            or existing.source_version_id != expected.source_version_id
            or existing.content_hash != expected.content_hash
            or existing.snapshot_json != expected.content
        ):
            raise self._invalid("The node already has different frozen inputs.")
        return True

    def _invalid(self, message: str) -> ApiError:
        return ApiError(status_code=409, code=self._error_code, message=message)
