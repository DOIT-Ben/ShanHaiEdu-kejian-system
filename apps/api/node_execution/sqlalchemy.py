"""SQLAlchemy transaction owner for the generic two-phase node executor."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.execution_port import SqlAlchemyArtifactPort
from apps.api.assets.execution_port import SqlAlchemyAssetPort
from apps.api.content_runtime.runtime_port import SqlAlchemyRuntimeDefinitionReader
from apps.api.creation.execution_port import SqlAlchemyCreationPackagePort
from apps.api.identity.context import ActorContext
from apps.api.model_gateway.contracts import TextGatewayResult
from apps.api.model_gateway.execution_port import AttemptEvidence, SqlAlchemyAttemptExecutionPort
from apps.api.node_execution.contracts import (
    CommittedNodeExecution,
    NodeExecutionCommitContext,
    NodeExecutionError,
    NodeExecutionTransaction,
    NodeExecutionTransactionFactory,
    PreparedNodeExecution,
)
from apps.api.node_execution.materials import (
    audit_context,
    collect_context_items,
    collect_upstream_artifacts,
    execution_snapshot,
    placeholder_request,
)
from apps.api.node_execution.prompt_plan import compile_node_prompt
from apps.api.prompt_runtime.execution_port import SqlAlchemyPromptSnapshotPort
from apps.api.runtime_boundary.output_projection import compile_output_projection
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

    def prepare(self, node_run_id: UUID, request_id: str) -> PreparedNodeExecution:
        execution = self._workflow.require_context(node_run_id, for_update=True)
        committed_version_id = self._workflow.committed_artifact(node_run_id)
        if committed_version_id is not None:
            self._workflow.require_execution_request(node_run_id, request_id)
            return self._prepare_committed(execution, committed_version_id, node_run_id)
        return self._prepare_new(execution, node_run_id, request_id)

    def _prepare_committed(
        self,
        execution: WorkflowExecutionContext,
        committed_version_id: UUID,
        node_run_id: UUID,
    ) -> PreparedNodeExecution:
        existing = self._artifacts.result_for_version(committed_version_id)
        request = self._artifacts.request_id_for_version(committed_version_id)
        evidence = self._attempts.require_succeeded(
            node_run_id=node_run_id,
            project_id=execution.project_id,
            request_id=request,
        )
        return PreparedNodeExecution(
            node_run_id=node_run_id,
            request=placeholder_request(request),
            audit_context=audit_context(execution, self._actor.user_id),
            output_schema={},
            committed_result=CommittedNodeExecution(
                node_run_id=node_run_id,
                artifact_version_id=existing.artifact_version_id,
                creation_package_id=self._packages.find_for_node(node_run_id),
                attempt_id=evidence.attempt_id,
                usage_id=evidence.usage_id,
            ),
        )

    def _prepare_new(
        self,
        execution: WorkflowExecutionContext,
        node_run_id: UUID,
        request_id: str,
    ) -> PreparedNodeExecution:
        (
            materials,
            compiled,
            snapshots,
            upstream,
            runtime_values,
            target_auth,
            reference_auth,
            succeeded,
            frozen_reference_assets,
        ) = self._compile_inputs(execution, node_run_id)
        self._workflow.freeze_execution(
            execution,
            request_id=request_id,
            snapshot=execution_snapshot(
                execution,
                compiled,
                snapshots,
                upstream,
                frozen_reference_assets,
            ),
        )
        if self._attempts.has_active_attempt(node_run_id):
            raise NodeExecutionError(
                "NODE_EXECUTION_IN_FLIGHT",
                "another worker already owns the frozen node execution",
            )
        owner_token = self._claim_owner(node_run_id)
        self._workflow.start(node_run_id)
        result_unavailable = succeeded is not None and succeeded.recovery_text is None
        return PreparedNodeExecution(
            node_run_id=node_run_id,
            request=compiled.request,
            audit_context=compiled.audit_context,
            output_schema=materials.output_schema,
            execution_owner_token=owner_token,
            pre_model_error_code=(
                "NODE_EXECUTION_RESULT_UNAVAILABLE" if result_unavailable else None
            ),
            pre_model_error_message=(
                "the successful model result was lost before T2" if result_unavailable else None
            ),
            recovered_result_text=(succeeded.recovery_text if succeeded is not None else None),
            commit_context=NodeExecutionCommitContext(
                definition=materials.definition,
                execution=execution,
                snapshots=snapshots,
                upstream_artifacts=upstream,
                runtime_values=runtime_values,
                target_slot_authorization=target_auth,
                reference_asset_authorization=reference_auth,
            ),
        )

    def _claim_owner(self, node_run_id: UUID) -> str:
        owner_token = str(uuid4())
        try:
            self._workflow.claim_execution_owner(node_run_id, owner_token)
        except Exception as exc:
            raise NodeExecutionError(
                getattr(exc, "code", "NODE_EXECUTION_IN_FLIGHT"),
                str(exc),
            ) from exc
        return owner_token

    def _compile_inputs(self, execution: WorkflowExecutionContext, node_run_id: UUID):
        materials = self._definitions.resolve_materials(node_run_id)
        binding = materials.definition.node_binding
        context_items = collect_context_items(self._artifacts, self._assets, execution, binding)
        upstream = collect_upstream_artifacts(self._artifacts, execution, binding)
        succeeded = self._attempts.succeeded_attempt(
            node_run_id=node_run_id,
            project_id=execution.project_id,
        )
        request_id = (
            succeeded.request_id
            if succeeded is not None
            else self._attempts.next_model_request_id(node_run_id)
        )
        compiled = compile_node_prompt(
            definition=materials.definition,
            execution=execution,
            prompt_template=materials.prompt_template,
            output_schema=materials.output_schema,
            context_items=context_items,
            request_id=request_id,
            user_id=self._actor.user_id,
        )
        snapshots = self._snapshots.freeze(
            node_run_id,
            context=compiled.context,
            prompt=compiled.prompt,
        )
        reference_auth = self._assets.freeze_reference_assets(materials.definition, execution)
        frozen_reference_assets = [
            {"asset_version_id": str(asset.asset_version_id), "role": asset.role}
            for asset in (reference_auth.assets if reference_auth is not None else ())
        ]
        return (
            materials,
            compiled,
            snapshots,
            upstream,
            ({"reference_assets": frozen_reference_assets} if reference_auth is not None else {}),
            self._assets.authorize_target_slots(materials.definition, execution),
            reference_auth,
            succeeded,
            frozen_reference_assets,
        )

    def commit(
        self,
        execution: PreparedNodeExecution,
        output: dict[str, Any],
        result: TextGatewayResult,
    ) -> CommittedNodeExecution:
        context = execution.commit_context
        if context is None:
            raise NodeExecutionError(
                "NODE_EXECUTION_CONTEXT_MISSING",
                "the prepared execution has no commit context",
            )
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
        self._definitions.resolve(execution.node_run_id)
        evidence = self._attempts.require_succeeded(
            node_run_id=current.node_run_id,
            project_id=current.project_id,
            request_id=execution.request.request_id,
        )
        return self._persist_outputs(execution, current, context, output, evidence, owner_token)

    def _persist_outputs(
        self,
        execution: PreparedNodeExecution,
        current: WorkflowExecutionContext,
        context: NodeExecutionCommitContext,
        output: dict[str, Any],
        evidence: AttemptEvidence,
        owner_token: str,
    ) -> CommittedNodeExecution:
        plan = compile_output_projection(
            definition=context.definition,
            execution=current,
            snapshots=context.snapshots,
            validated_output=output,
            upstream_artifacts=context.upstream_artifacts,
            request_id=execution.request.request_id,
            runtime_values=context.runtime_values,
            target_slot_authorization=context.target_slot_authorization,
            reference_asset_authorization=context.reference_asset_authorization,
        )
        artifact_result = self._artifacts.persist_generated(plan.artifact_write)
        self._fault_injector("after_artifact")
        package_result = None
        from apps.api.runtime_boundary.projection_package import materialize_creation_package

        package = materialize_creation_package(plan, artifact_result=artifact_result)
        if package is not None:
            package_result = self._packages.publish(package)
        self._fault_injector("after_package")
        self._fault_injector("before_transition")
        self._workflow.release_execution_owner(execution.node_run_id, owner_token)
        self._workflow.complete(execution.node_run_id, artifact_result.artifact_version_id)
        return CommittedNodeExecution(
            node_run_id=execution.node_run_id,
            artifact_version_id=artifact_result.artifact_version_id,
            creation_package_id=(
                package_result.creation_package_id if package_result is not None else None
            ),
            attempt_id=evidence.attempt_id,
            usage_id=evidence.usage_id,
        )

    def terminalize_failure(
        self,
        execution: PreparedNodeExecution,
        *,
        code: str,
        cancelled: bool,
    ) -> None:
        owner_token = execution.execution_owner_token
        if owner_token is not None:
            if not self._workflow.owns_execution_owner(execution.node_run_id, owner_token):
                return
            self._workflow.release_execution_owner(execution.node_run_id, owner_token)
        self._workflow.terminalize(
            execution.node_run_id,
            code=code,
            cancelled=cancelled,
        )


def _ignore_fault_stage(_stage: str) -> None:
    return None
