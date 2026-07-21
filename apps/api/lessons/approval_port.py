"""Lesson-owned approval completion port for declared lesson-unit synchronization."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.domain import (
    ImpactSelector,
    StaleImpactDimension,
    StaleImpactSelection,
)
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.content_runtime.approval_port import ContentDefinitionApprovalReader
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.lessons.division_runtime import (
    build_approved_lesson_division,
    diff_lesson_divisions,
)
from apps.api.lessons.repository import LessonRepository
from apps.api.lessons.service import LessonService
from apps.api.projects.models import Project
from apps.api.workflows.approval_port import WorkflowApprovalReader
from apps.api.workflows.lesson_fanout import (
    LessonFanoutTarget,
    LessonWorkflowFanoutService,
)
from apps.api.workflows.models import NodeRun, WorkflowRun
from apps.api.workflows.service import WorkflowRuntimeService
from workflow.definition import WorkflowOutputDefinitionBinding
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY


@dataclass(frozen=True, slots=True)
class LessonApprovalCompletionResult:
    stale_selection: StaleImpactSelection
    lesson_count: int


class LessonDivisionApprovalPort:
    """Apply only the completion effect explicitly declared by the fixed release."""

    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def apply(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        *,
        previous_version_id: UUID | None,
        project: Project,
        request_id: str | None,
    ) -> LessonApprovalCompletionResult | None:
        output = self._declared_output(artifact, project)
        if output is None or output.approval_completion is None:
            return None
        completion = output.approval_completion
        if completion.kind != "lesson_unit_sync":
            raise self._invalid("The declared approval completion is unsupported.")
        run = self._require_source_run(artifact, version, project, output)
        previous = self._previous_content(previous_version_id)
        diff = diff_lesson_divisions(previous, version.content_json)
        division = build_approved_lesson_division(version.id, version.content_json)

        repository = LessonRepository(self._session, self._actor)
        existing = repository.list_for_project(
            artifact.project_id,
            include_archived=True,
            for_update=True,
        )
        by_key = {lesson.lesson_key: lesson for lesson in existing}
        archived_ids = tuple(by_key[key].id for key in diff.archived_keys if key in by_key)
        fanout = LessonWorkflowFanoutService(self._session, self._actor)
        fanout.lock_archivable(run.id, archived_ids)
        active = LessonService(self._session, self._actor).synchronize_approved_division(
            artifact.project_id,
            division,
            request_id=request_id,
        )
        targets = tuple(
            LessonFanoutTarget(
                lesson_unit_id=lesson.id,
                branch_enabled={
                    config.branch_key: config.enabled
                    for config in repository.list_branch_configs(lesson.id, for_update=True)
                },
            )
            for lesson in active
        )
        fanout.synchronize(
            run.id,
            targets=targets,
            archived_lesson_unit_ids=archived_ids,
            request_id=request_id,
        )
        self._complete_gate(run, output)
        return LessonApprovalCompletionResult(
            stale_selection=StaleImpactSelection.exact(
                (
                    StaleImpactDimension(
                        selector=ImpactSelector.LESSON_KEY,
                        changed_keys=diff.changed_keys,
                        archived_keys=diff.archived_keys,
                    ),
                )
            ),
            lesson_count=len(active),
        )

    def _declared_output(
        self,
        artifact: Artifact,
        project: Project,
    ) -> WorkflowOutputDefinitionBinding | None:
        definition_key = ContentDefinitionApprovalReader(self._session).definition_key(
            definition_id=artifact.content_definition_version_id,
            content_release_id=project.content_release_id,
        )
        graph = WorkflowApprovalReader(self._session).published_graph(
            project.workflow_definition_version_id
        )
        if definition_key is None or graph is None:
            raise self._invalid("The fixed content or workflow release is unavailable.")
        registered = BUILTIN_WORKFLOW_REGISTRY.load(graph)
        return registered.output_definition_index.get(definition_key)

    def _require_source_run(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        project: Project,
        output: WorkflowOutputDefinitionBinding,
    ) -> WorkflowRun:
        if version.source_node_run_id is None:
            raise self._invalid("A declared lesson completion requires a generated source node.")
        node = self._session.scalar(
            select(NodeRun)
            .where(
                NodeRun.id == version.source_node_run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.node_key == output.producer_node_key,
                NodeRun.branch_run_id.is_(None),
                NodeRun.deleted_at.is_(None),
            )
            .with_for_update(of=NodeRun)
        )
        run = self._session.get(WorkflowRun, node.workflow_run_id) if node is not None else None
        if (
            node is None
            or run is None
            or run.organization_id != self._actor.organization_id
            or run.project_id != artifact.project_id
            or run.workflow_definition_version_id != project.workflow_definition_version_id
            or run.content_release_id != project.content_release_id
        ):
            raise self._invalid("The generated lesson division is outside the fixed workflow run.")
        return run

    def _complete_gate(
        self,
        run: WorkflowRun,
        output: WorkflowOutputDefinitionBinding,
    ) -> None:
        gate_key = output.quality_gate_node_key
        if gate_key is None:
            raise self._invalid("The lesson approval gate is not declared.")
        gate = self._session.scalar(
            select(NodeRun)
            .where(
                NodeRun.workflow_run_id == run.id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.branch_run_id.is_(None),
                NodeRun.node_key == gate_key,
                NodeRun.deleted_at.is_(None),
            )
            .order_by(NodeRun.run_no.desc())
            .limit(1)
            .with_for_update(of=NodeRun)
        )
        if gate is None or NodeStatus(gate.status) is not NodeStatus.REVIEW_REQUIRED:
            raise self._invalid("The exact lesson approval gate is not awaiting review.")
        WorkflowRuntimeService(self._session, self._actor).transition_node(
            gate.id,
            NodeStatus.APPROVED,
        )

    def _previous_content(self, version_id: UUID | None) -> dict[str, object] | None:
        if version_id is None:
            return None
        version = self._session.get(ArtifactVersion, version_id)
        if version is None or version.organization_id != self._actor.organization_id:
            raise self._invalid("The previous approved lesson division is unavailable.")
        return version.content_json

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(
            status_code=409,
            code="LESSON_DIVISION_APPROVAL_INVALID",
            message=message,
        )
