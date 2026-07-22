"""SQLAlchemy transaction owner for the generic two-phase node executor."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.execution_port import SqlAlchemyArtifactPort
from apps.api.assets.execution_port import SqlAlchemyAssetPort
from apps.api.content_runtime.runtime_port import (
    RuntimeNodeMaterials,
    SqlAlchemyRuntimeDefinitionReader,
)
from apps.api.creation.execution_port import SqlAlchemyCreationPackagePort
from apps.api.identity.context import ActorContext
from apps.api.model_gateway.execution_port import (
    SqlAlchemyAttemptExecutionPort,
    SucceededAttempt,
)
from apps.api.model_gateway.pending import PendingTextGeneration
from apps.api.node_execution.boundaries import same_fixed_execution
from apps.api.node_execution.contracts import (
    CommittedNodeExecution,
    NodeExecutionCommitContext,
    NodeExecutionError,
    NodeExecutionTransaction,
    NodeExecutionTransactionFactory,
    PreparedNodeExecution,
)
from apps.api.node_execution.fresh_inputs import compile_fresh_inputs
from apps.api.node_execution.materials import (
    audit_context,
    execution_snapshot,
)
from apps.api.node_execution.preparation import (
    build_frozen_invocation,
    build_prepared_execution,
    build_recovered_execution,
    frozen_model_request,
    frozen_upstream_refs,
    recover_commit_context,
)
from apps.api.node_execution.recovery import SqlAlchemyRecoveryFactStore
from apps.api.node_execution.transaction_steps import (
    claim_execution_owner,
    persist_execution_outputs,
    prepare_cancel_requested_execution,
    prepare_committed_execution,
    terminalize_execution_failure,
)
from apps.api.prompt_runtime.execution_port import SqlAlchemyPromptSnapshotPort
from apps.api.runtime_boundary.ports import PromptSnapshotPort, WorkflowExecutionContext
from apps.api.workflows.execution_port import SqlAlchemyWorkflowExecutionPort
from workflow.node_state import NodeStatus


class SqlAlchemyNodeExecutionTransactionFactory(NodeExecutionTransactionFactory):
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        actor: ActorContext,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._actor = actor
        self._fault_injector: Callable[[str], None] = fault_injector or _ignore_fault_stage

    @contextmanager
    def begin(self) -> Generator[NodeExecutionTransaction]:
        session = self._session_factory()
        try:
            with session.begin():
                yield SqlAlchemyNodeExecutionTransaction(
                    session,
                    self._actor,
                    fault_injector=self._fault_injector,
                )
        finally:
            session.close()


class SqlAlchemyNodeExecutionTransaction(NodeExecutionTransaction):
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        fault_injector: Callable[[str], None],
    ) -> None:
        self._session = session
        self._actor = actor
        self._workflow: SqlAlchemyWorkflowExecutionPort = SqlAlchemyWorkflowExecutionPort(
            session, actor
        )
        self._definitions = SqlAlchemyRuntimeDefinitionReader(session, actor, self._workflow)
        self._artifacts: SqlAlchemyArtifactPort = SqlAlchemyArtifactPort(session, actor)
        self._assets: SqlAlchemyAssetPort = SqlAlchemyAssetPort(session, actor)
        self._snapshots: PromptSnapshotPort = SqlAlchemyPromptSnapshotPort(session, actor)
        self._packages: SqlAlchemyCreationPackagePort = SqlAlchemyCreationPackagePort(
            session, actor
        )
        self._attempts = SqlAlchemyAttemptExecutionPort(session, actor)
        self._fault_injector = fault_injector
        self._recovery = SqlAlchemyRecoveryFactStore(
            session,
            actor,
            self._attempts,
            fault_injector,
        )

    def prepare(self, node_run_id: UUID, request_id: str) -> PreparedNodeExecution:
        execution = self._workflow.require_context(node_run_id, for_update=True)
        if execution.status == NodeStatus.CANCEL_REQUESTED.value:
            return prepare_cancel_requested_execution(execution, request_id, self._actor.user_id)
        committed_version_id = self._workflow.committed_artifact(node_run_id)
        if committed_version_id is not None:
            self._workflow.require_execution_request(node_run_id, request_id)
            return prepare_committed_execution(
                execution=execution,
                committed_version_id=committed_version_id,
                node_run_id=node_run_id,
                user_id=self._actor.user_id,
                artifacts=self._artifacts,
                attempts=self._attempts,
                packages=self._packages,
            )
        return self._prepare_new(execution, node_run_id, request_id)

    def _prepare_new(
        self,
        execution: WorkflowExecutionContext,
        node_run_id: UUID,
        request_id: str,
    ) -> PreparedNodeExecution:
        succeeded = self._attempts.succeeded_attempt(
            node_run_id=node_run_id,
            project_id=execution.project_id,
        )
        frozen = self._workflow.find_frozen_execution_snapshot(node_run_id, request_id)
        if frozen is not None:
            if succeeded is not None:
                return self._prepare_recovery(execution, node_run_id, frozen, succeeded)
            return self._prepare_frozen_invocation(execution, node_run_id, frozen)
        return self._prepare_fresh(execution, node_run_id, request_id)

    def _prepare_fresh(
        self,
        execution: WorkflowExecutionContext,
        node_run_id: UUID,
        request_id: str,
    ) -> PreparedNodeExecution:
        inputs = compile_fresh_inputs(
            definitions=self._definitions,
            artifacts=self._artifacts,
            assets=self._assets,
            snapshots=self._snapshots,
            execution=execution,
            node_run_id=node_run_id,
            model_request_id=self._attempts.next_model_request_id(node_run_id),
            user_id=self._actor.user_id,
        )
        self._workflow.freeze_execution(
            execution,
            request_id=request_id,
            snapshot=execution_snapshot(
                execution,
                inputs.compiled,
                inputs.snapshots,
                inputs.upstream,
                inputs.frozen_reference_assets,
                target_slots=(
                    inputs.target_authorization.slots
                    if inputs.target_authorization is not None
                    else ()
                ),
                reference_assets_authorized=inputs.reference_authorization is not None,
            ),
        )
        if self._attempts.has_active_attempt(node_run_id):
            raise NodeExecutionError(
                "NODE_EXECUTION_IN_FLIGHT",
                "another worker already owns the frozen node execution",
            )
        owner_token = claim_execution_owner(self._workflow, node_run_id)
        self._workflow.start(node_run_id)
        return build_prepared_execution(
            node_run_id=node_run_id,
            execution=execution,
            materials=inputs.materials,
            compiled=inputs.compiled,
            snapshots=inputs.snapshots,
            upstream=inputs.upstream,
            runtime_values=inputs.runtime_values,
            target_authorization=inputs.target_authorization,
            reference_authorization=inputs.reference_authorization,
            succeeded=None,
            recovery_state="none",
            owner_token=owner_token,
        )

    def _prepare_recovery(
        self,
        execution: WorkflowExecutionContext,
        node_run_id: UUID,
        frozen: dict[str, Any],
        succeeded: SucceededAttempt,
    ) -> PreparedNodeExecution:
        materials, context = self._load_frozen_context(execution, node_run_id, frozen)
        request = frozen_model_request(frozen).model_copy(
            update={"request_id": succeeded.request_id}
        )
        if self._attempts.has_active_attempt(node_run_id):
            raise NodeExecutionError(
                "NODE_EXECUTION_IN_FLIGHT",
                "another worker already owns the frozen node execution",
            )
        owner_token = claim_execution_owner(self._workflow, node_run_id)
        recovery_state = self._recovery.state(execution, succeeded, succeeded.request_id)
        if recovery_state == "available":
            self._recovery.rebind_owner(
                execution,
                succeeded,
                succeeded.request_id,
                owner_token,
            )
        self._workflow.start(node_run_id)
        return build_recovered_execution(
            node_run_id=node_run_id,
            request=request,
            audit_context=audit_context(execution, self._actor.user_id),
            output_schema=materials.output_schema,
            commit_context=context,
            succeeded=succeeded,
            recovery_state=recovery_state,
            owner_token=owner_token,
        )

    def _prepare_frozen_invocation(
        self,
        execution: WorkflowExecutionContext,
        node_run_id: UUID,
        frozen: dict[str, Any],
    ) -> PreparedNodeExecution:
        materials, context = self._load_frozen_context(execution, node_run_id, frozen)
        request = frozen_model_request(frozen)
        if self._attempts.status_for_request(node_run_id, request.request_id) is not None:
            request = request.model_copy(
                update={"request_id": self._attempts.next_model_request_id(node_run_id)}
            )
        if self._attempts.has_active_attempt(node_run_id):
            raise NodeExecutionError(
                "NODE_EXECUTION_IN_FLIGHT",
                "another worker already owns the frozen node execution",
            )
        owner_token = claim_execution_owner(self._workflow, node_run_id)
        self._workflow.start(node_run_id)
        return build_frozen_invocation(
            node_run_id=node_run_id,
            request=request,
            audit_context=audit_context(execution, self._actor.user_id),
            output_schema=materials.output_schema,
            commit_context=context,
            owner_token=owner_token,
        )

    def _load_frozen_context(
        self,
        execution: WorkflowExecutionContext,
        node_run_id: UUID,
        frozen: dict[str, Any],
    ) -> tuple[RuntimeNodeMaterials, NodeExecutionCommitContext]:
        materials = self._definitions.resolve_materials(node_run_id)
        snapshots = self._snapshots.load_frozen(node_run_id)
        upstream = self._artifacts.load_frozen_versions(
            execution,
            frozen_upstream_refs(frozen),
        )
        context = recover_commit_context(
            materials=materials,
            execution=execution,
            snapshots=snapshots,
            upstream=upstream,
            frozen=frozen,
        )
        return materials, context

    def checkpoint(
        self,
        execution: PreparedNodeExecution,
        output: dict[str, Any],
        pending: PendingTextGeneration,
    ) -> None:
        context = execution.commit_context
        if context is None:
            raise NodeExecutionError(
                "NODE_EXECUTION_CONTEXT_MISSING",
                "the prepared execution has no commit context",
            )
        owner_token, current = self._require_owned_running(execution)
        self._recovery.checkpoint(execution, current, context, owner_token, output, pending)

    def commit(self, execution: PreparedNodeExecution) -> CommittedNodeExecution:
        context = execution.commit_context
        if context is None:
            raise NodeExecutionError(
                "NODE_EXECUTION_CONTEXT_MISSING",
                "the prepared execution has no commit context",
            )
        owner_token, current = self._require_owned_running(execution)
        fact = self._recovery.require(execution, current, context, owner_token)
        self._definitions.resolve(execution.node_run_id)
        self._snapshots.verify(context.snapshots)
        self._artifacts.verify_frozen_versions(current, context.upstream_artifacts)
        evidence = self._attempts.require_succeeded(
            node_run_id=current.node_run_id,
            project_id=current.project_id,
            request_id=execution.request.request_id,
        )
        if evidence.attempt_id != fact.attempt_id:
            raise NodeExecutionError(
                "NODE_EXECUTION_RECOVERY_MISMATCH",
                "the recovery fact is not bound to the successful attempt",
            )
        result = persist_execution_outputs(
            execution=execution,
            current=current,
            context=context,
            output=fact.output_json,
            evidence=evidence,
            owner_token=owner_token,
            artifacts=self._artifacts,
            packages=self._packages,
            workflow=self._workflow,
            fault_injector=self._fault_injector,
        )
        self._session.delete(fact)
        self._session.flush()
        return result

    def _require_owned_running(
        self,
        execution: PreparedNodeExecution,
    ) -> tuple[str, WorkflowExecutionContext]:
        owner_token = execution.execution_owner_token
        if owner_token is None or not self._workflow.owns_execution_owner(
            execution.node_run_id, owner_token
        ):
            raise NodeExecutionError(
                "NODE_EXECUTION_OWNER_LOST",
                "the worker no longer owns the node execution",
            )
        current = self._workflow.require_context(execution.node_run_id, for_update=True)
        if current.status == NodeStatus.CANCEL_REQUESTED.value:
            raise NodeExecutionError(
                "NODE_EXECUTION_CANCEL_REQUESTED",
                "the node run was cancelled before T2",
            )
        if current.status != NodeStatus.RUNNING.value:
            raise NodeExecutionError(
                "NODE_EXECUTION_STATE_CONFLICT",
                "the node run is not running at T2",
            )
        commit_context = execution.commit_context
        if commit_context is None:
            raise NodeExecutionError(
                "NODE_EXECUTION_CONTEXT_MISSING",
                "the prepared execution has no commit context",
            )
        if not same_fixed_execution(current, commit_context.execution):
            raise NodeExecutionError(
                "NODE_EXECUTION_CONTEXT_CHANGED",
                "the fixed workflow execution context changed before commit",
            )
        return owner_token, current

    def terminalize_failure(
        self,
        execution: PreparedNodeExecution,
        *,
        code: str,
        cancelled: bool,
    ) -> None:
        terminalize_execution_failure(
            execution=execution,
            code=code,
            cancelled=cancelled,
            workflow=self._workflow,
            recovery=self._recovery,
        )


def _ignore_fault_stage(_stage: str) -> None:
    return None
