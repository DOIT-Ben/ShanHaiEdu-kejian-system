"""Database guard for the trusted generated Artifact write capability."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.execution_errors import ArtifactExecutionPortError
from apps.api.content_runtime.authoring_policy import AuthoringPolicyUnavailable
from apps.api.content_runtime.authoring_policy_loader import AuthoringPolicyLoader
from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageVersion,
    ContentReleaseItem,
)
from apps.api.identity.context import ActorContext
from apps.api.projects.models import Project
from apps.api.prompt_runtime.models import ContextSnapshot, PromptSnapshot
from apps.api.runtime_boundary.ports import GeneratedArtifactWrite
from apps.api.workflows.models import BranchRun, NodeRun, WorkflowRun
from workflow.node_state import NodeStatus


class GeneratedArtifactWriteGuard:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require(self, write: GeneratedArtifactWrite) -> None:
        row = self._session.execute(
            select(NodeRun, WorkflowRun, Project)
            .join(WorkflowRun, WorkflowRun.id == NodeRun.workflow_run_id)
            .join(Project, Project.id == WorkflowRun.project_id)
            .where(
                NodeRun.id == write.node_run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.deleted_at.is_(None),
                NodeRun.status == NodeStatus.RUNNING.value,
                WorkflowRun.organization_id == self._actor.organization_id,
                WorkflowRun.project_id == write.project_id,
                WorkflowRun.content_release_id == Project.content_release_id,
                WorkflowRun.workflow_definition_version_id
                == Project.workflow_definition_version_id,
                Project.organization_id == self._actor.organization_id,
                Project.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            raise self._provenance_error()
        node, _run, _project = row
        self._require_branch_scope(node, write)
        self._require_snapshots(write)
        definition = self._require_definition(write)
        try:
            AuthoringPolicyLoader(self._session).require(definition)
        except AuthoringPolicyUnavailable as exc:
            raise ArtifactExecutionPortError(
                "AUTHORING_POLICY_UNAVAILABLE",
                "the generated artifact definition has no published authoring policy",
            ) from exc

    def _require_branch_scope(self, node: NodeRun, write: GeneratedArtifactWrite) -> None:
        if node.branch_run_id is None:
            if write.lesson_unit_id is not None or write.branch_key != "project":
                raise self._provenance_error()
            return
        branch = self._session.scalar(select(BranchRun).where(BranchRun.id == node.branch_run_id))
        if (
            branch is None
            or branch.lesson_unit_id != write.lesson_unit_id
            or branch.branch_key != write.branch_key
        ):
            raise self._provenance_error()

    def _require_snapshots(self, write: GeneratedArtifactWrite) -> None:
        snapshot = self._session.execute(
            select(ContextSnapshot, PromptSnapshot)
            .join(
                PromptSnapshot,
                PromptSnapshot.context_snapshot_id == ContextSnapshot.id,
            )
            .where(
                ContextSnapshot.id == write.context_snapshot_id,
                ContextSnapshot.organization_id == self._actor.organization_id,
                ContextSnapshot.project_id == write.project_id,
                ContextSnapshot.node_run_id == write.node_run_id,
                PromptSnapshot.id == write.prompt_snapshot_id,
                PromptSnapshot.organization_id == self._actor.organization_id,
                PromptSnapshot.project_id == write.project_id,
                PromptSnapshot.node_run_id == write.node_run_id,
            )
        ).one_or_none()
        if snapshot is None:
            raise self._provenance_error()

    def _require_definition(self, write: GeneratedArtifactWrite) -> ContentDefinitionVersion:
        definition = self._session.scalar(
            select(ContentDefinitionVersion)
            .join(
                ContentPackageVersion,
                ContentPackageVersion.id == ContentDefinitionVersion.content_package_version_id,
            )
            .join(
                ContentReleaseItem,
                ContentReleaseItem.content_package_version_id == ContentPackageVersion.id,
            )
            .join(Project, Project.content_release_id == ContentReleaseItem.content_release_id)
            .where(
                ContentDefinitionVersion.id == write.content_definition_version_id,
                ContentPackageVersion.status == "published",
                Project.id == write.project_id,
                Project.organization_id == self._actor.organization_id,
            )
        )
        if definition is None:
            raise self._provenance_error()
        return definition

    @staticmethod
    def _provenance_error() -> ArtifactExecutionPortError:
        return ArtifactExecutionPortError(
            "NODE_EXECUTION_ARTIFACT_PROVENANCE_INVALID",
            "the generated artifact write does not match its frozen execution",
        )
