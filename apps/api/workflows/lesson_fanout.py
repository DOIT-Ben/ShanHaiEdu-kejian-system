"""Published-topology lesson branch fanout contracts and SQL application service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.workflows.lesson_fanout_contracts import (
    LessonBranchFanoutPlan,
    LessonFanoutResult,
    LessonFanoutTarget,
    build_lesson_fanout_plan,
)
from apps.api.workflows.models import BranchRun, NodeRun, WorkflowDefinitionVersion, WorkflowRun
from apps.api.workflows.repository import WorkflowRuntimeRepository
from apps.api.workflows.service import WorkflowRuntimeService
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

_ACTIVE_EXECUTION_STATUSES = frozenset(
    {NodeStatus.QUEUED.value, NodeStatus.RUNNING.value, NodeStatus.CANCEL_REQUESTED.value}
)


class LessonWorkflowFanoutService:
    """Create and archive lesson runs while workflows remains the ORM owner."""

    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = WorkflowRuntimeRepository(session, actor)

    def synchronize(
        self,
        workflow_run_id: UUID,
        *,
        targets: tuple[LessonFanoutTarget, ...],
        archived_lesson_unit_ids: tuple[UUID, ...],
        request_id: str | None,
    ) -> LessonFanoutResult:
        run = self._repository.get_run(workflow_run_id, for_update=True)
        if run is None:
            raise self._not_found()
        ProjectAccessService(self._session, self._actor).require(
            run.project_id,
            ProjectAction.EDIT,
            for_update=True,
        )
        return self._synchronize_run(
            run,
            targets=targets,
            archived_lesson_unit_ids=archived_lesson_unit_ids,
            request_id=request_id,
        )

    def synchronize_declared_approval(
        self,
        workflow_run_id: UUID,
        *,
        targets: tuple[LessonFanoutTarget, ...],
        archived_lesson_unit_ids: tuple[UUID, ...],
        request_id: str | None,
    ) -> LessonFanoutResult:
        run = self._repository.get_run(workflow_run_id, for_update=True)
        if run is None:
            raise self._not_found()
        ProjectAccessService(self._session, self._actor).require_review_completion(
            run.project_id,
            for_update=True,
        )
        return self._synchronize_run(
            run,
            targets=targets,
            archived_lesson_unit_ids=archived_lesson_unit_ids,
            request_id=request_id,
        )

    def synchronize_lesson_configuration(
        self,
        project_id: UUID,
        target: LessonFanoutTarget,
        *,
        request_id: str | None,
    ) -> LessonFanoutResult | None:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.EDIT,
            for_update=True,
        )
        run = self._repository.active_for_project(project_id, for_update=True)
        if run is None:
            return None
        return self._synchronize_run(
            run,
            targets=(target,),
            archived_lesson_unit_ids=(),
            request_id=request_id,
        )

    def _synchronize_run(
        self,
        run: WorkflowRun,
        *,
        targets: tuple[LessonFanoutTarget, ...],
        archived_lesson_unit_ids: tuple[UUID, ...],
        request_id: str | None,
    ) -> LessonFanoutResult:
        workflow = self._session.get(WorkflowDefinitionVersion, run.workflow_definition_version_id)
        if workflow is None or workflow.status != "published":
            raise self._invalid("The fixed workflow definition is unavailable.")
        registered = BUILTIN_WORKFLOW_REGISTRY.load(workflow.graph_json)
        plans = build_lesson_fanout_plan(registered)
        expected_branches = {plan.branch_key for plan in plans}
        self._validate_targets(targets, expected_branches)

        archived_count = self._archive_branches(run.id, archived_lesson_unit_ids)
        created_branches = 0
        created_nodes = 0
        for target in sorted(targets, key=lambda item: str(item.lesson_unit_id)):
            for plan in plans:
                branch, created = self._ensure_branch(
                    run.id,
                    target.lesson_unit_id,
                    plan.branch_key,
                    enabled=target.branch_enabled[plan.branch_key],
                )
                created_branches += int(created)
                created_nodes += self._ensure_entrypoints(
                    run,
                    branch,
                    plan,
                    enabled=target.branch_enabled[plan.branch_key],
                )
        changed = created_branches + created_nodes + archived_count
        if changed:
            EventWriter(self._session, self._actor.organization_id).append(
                project_id=run.project_id,
                event_type="workflow.lesson_branches.synchronized",
                resource=EventResource(type="workflow_run", id=run.id),
                payload={
                    "created_branch_count": created_branches,
                    "created_node_count": created_nodes,
                    "archived_branch_count": archived_count,
                },
                request_id=request_id,
            )
        return LessonFanoutResult(created_branches, created_nodes, archived_count)

    def lock_archivable(
        self,
        workflow_run_id: UUID,
        lesson_unit_ids: tuple[UUID, ...],
    ) -> None:
        """Lock archive candidates and reject any still-active execution."""

        self._lock_archive_branches(workflow_run_id, lesson_unit_ids)

    def _archive_branches(
        self,
        workflow_run_id: UUID,
        lesson_unit_ids: tuple[UUID, ...],
    ) -> int:
        branches = self._lock_archive_branches(workflow_run_id, lesson_unit_ids)
        changed = 0
        now = utc_now()
        for branch in branches:
            if branch.status == "cancelled":
                continue
            branch.status = "cancelled"
            branch.completed_at = now
            self._touch(branch)
            changed += 1
        self._session.flush()
        return changed

    def _lock_archive_branches(
        self,
        workflow_run_id: UUID,
        lesson_unit_ids: tuple[UUID, ...],
    ) -> list[BranchRun]:
        if not lesson_unit_ids:
            return []
        branches = list(
            self._session.scalars(
                select(BranchRun)
                .where(
                    BranchRun.workflow_run_id == workflow_run_id,
                    BranchRun.lesson_unit_id.in_(lesson_unit_ids),
                    BranchRun.deleted_at.is_(None),
                )
                .order_by(BranchRun.id)
                .with_for_update(of=BranchRun)
            )
        )
        branch_ids = [branch.id for branch in branches]
        nodes = (
            list(
                self._session.scalars(
                    select(NodeRun)
                    .where(
                        NodeRun.branch_run_id.in_(branch_ids),
                        NodeRun.organization_id == self._actor.organization_id,
                        NodeRun.deleted_at.is_(None),
                    )
                    .order_by(NodeRun.id)
                    .with_for_update(of=NodeRun)
                )
            )
            if branch_ids
            else []
        )
        if any(node.status in _ACTIVE_EXECUTION_STATUSES for node in nodes):
            raise ApiError(
                status_code=409,
                code="LESSON_ARCHIVE_EXECUTION_ACTIVE",
                message="Cancel active lesson executions before archiving the lesson.",
            )
        return branches

    def _ensure_branch(
        self,
        workflow_run_id: UUID,
        lesson_unit_id: UUID,
        branch_key: str,
        *,
        enabled: bool,
    ) -> tuple[BranchRun, bool]:
        branch = self._session.scalar(
            select(BranchRun)
            .where(
                BranchRun.workflow_run_id == workflow_run_id,
                BranchRun.lesson_unit_id == lesson_unit_id,
                BranchRun.branch_key == branch_key,
                BranchRun.deleted_at.is_(None),
            )
            .with_for_update(of=BranchRun)
        )
        desired = "active" if enabled else "disabled"
        if branch is not None:
            if not enabled:
                self._require_branch_idle(branch.id)
            if branch.status != desired:
                branch.status = desired
                branch.completed_at = None
                if enabled and branch.started_at is None:
                    branch.started_at = utc_now()
                self._touch(branch)
            return branch, False
        branch = BranchRun(
            id=new_uuid7(),
            workflow_run_id=workflow_run_id,
            lesson_unit_id=lesson_unit_id,
            branch_key=branch_key,
            status=desired,
            started_at=utc_now() if enabled else None,
            completed_at=None,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(branch)
        self._session.flush()
        return branch, True

    def _ensure_entrypoints(
        self,
        run: WorkflowRun,
        branch: BranchRun,
        plan: LessonBranchFanoutPlan,
        *,
        enabled: bool,
    ) -> int:
        created = 0
        for node_key, dependencies in zip(
            plan.entrypoint_node_keys,
            plan.entrypoint_dependencies,
            strict=True,
        ):
            if dependencies:
                raise self._invalid("A published lesson entrypoint cannot have dependencies.")
            existing = self._session.scalar(
                select(NodeRun)
                .where(
                    NodeRun.workflow_run_id == run.id,
                    NodeRun.branch_run_id == branch.id,
                    NodeRun.node_key == node_key,
                    NodeRun.deleted_at.is_(None),
                )
                .order_by(NodeRun.run_no.desc())
                .limit(1)
                .with_for_update(of=NodeRun)
            )
            desired = NodeStatus.READY.value if enabled else NodeStatus.DISABLED.value
            if self._reuse_existing_entrypoint(existing, desired, enabled=enabled):
                continue
            node = NodeRun(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                workflow_run_id=run.id,
                branch_run_id=branch.id,
                node_key=node_key,
                run_no=self._repository.next_node_run_no(run.id, branch.id, node_key),
                status=desired,
                trigger_type="system",
                automation_policy_snapshot_json=run.automation_policy_snapshot_json,
                created_by=self._actor.principal_id,
                updated_by=self._actor.principal_id,
            )
            self._session.add(node)
            self._session.flush()
            created += 1
        return created

    def _reuse_existing_entrypoint(
        self,
        existing: NodeRun | None,
        desired: str,
        *,
        enabled: bool,
    ) -> bool:
        if existing is None:
            return False
        if existing.status == desired:
            return True
        if not enabled and existing.status in {
            NodeStatus.NOT_READY.value,
            NodeStatus.READY.value,
        }:
            WorkflowRuntimeService(self._session, self._actor).transition_node(
                existing.id,
                NodeStatus.DISABLED,
            )
            return True
        return existing.status not in {
            NodeStatus.DISABLED.value,
            NodeStatus.CANCELLED.value,
            NodeStatus.SKIPPED.value,
        }

    def _require_branch_idle(self, branch_run_id: UUID) -> None:
        active = self._session.scalar(
            select(NodeRun.id)
            .where(
                NodeRun.branch_run_id == branch_run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.status.in_(_ACTIVE_EXECUTION_STATUSES),
                NodeRun.deleted_at.is_(None),
            )
            .order_by(NodeRun.id)
            .limit(1)
            .with_for_update()
        )
        if active is not None:
            raise ApiError(
                status_code=409,
                code="LESSON_BRANCH_EXECUTION_ACTIVE",
                message="Cancel active lesson executions before disabling the branch.",
            )

    @staticmethod
    def _validate_targets(
        targets: tuple[LessonFanoutTarget, ...],
        expected_branches: set[str],
    ) -> None:
        lesson_ids = [target.lesson_unit_id for target in targets]
        if len(lesson_ids) != len(set(lesson_ids)):
            raise LessonWorkflowFanoutService._invalid("Lesson fanout targets are duplicated.")
        for target in targets:
            if set(target.branch_enabled) != expected_branches:
                raise LessonWorkflowFanoutService._invalid(
                    "Lesson branch configuration does not match the fixed workflow."
                )

    def _touch(self, record: BranchRun) -> None:
        record.updated_at = utc_now()
        record.updated_by = self._actor.principal_id
        record.lock_version += 1

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(status_code=404, code="WORKFLOW_RUN_NOT_FOUND", message="Run not found.")

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(status_code=409, code="LESSON_FANOUT_INVALID", message=message)
