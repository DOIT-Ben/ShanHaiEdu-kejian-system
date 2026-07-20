"""SQLAlchemy transaction owner for the generic two-phase node executor."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.execution_port import SqlAlchemyArtifactPort
from apps.api.assets.execution_port import SqlAlchemyAssetPort
from apps.api.content_runtime.runtime_port import SqlAlchemyRuntimeDefinitionReader
from apps.api.creation.execution_port import SqlAlchemyCreationPackagePort
from apps.api.identity.context import ActorContext
from apps.api.model_gateway.contracts import (
    ModelAuditContext,
    ModelCapability,
    TextGatewayResult,
    TextModelRequest,
)
from apps.api.model_gateway.execution_port import SqlAlchemyAttemptExecutionPort
from apps.api.node_execution.contracts import (
    CommittedNodeExecution,
    NodeExecutionCommitContext,
    NodeExecutionError,
    NodeExecutionTransaction,
    NodeExecutionTransactionFactory,
    PreparedNodeExecution,
)
from apps.api.node_execution.prompt_plan import CompiledNodePrompt, compile_node_prompt
from apps.api.prompt_runtime.execution_port import SqlAlchemyPromptSnapshotPort
from apps.api.runtime_boundary.output_projection import compile_output_projection
from apps.api.runtime_boundary.ports import (
    ArtifactContextVersion,
    AssetContextItem,
    FrozenSnapshotRefs,
    PromptSnapshotPort,
    WorkflowExecutionContext,
)
from apps.api.workflows.execution_port import SqlAlchemyWorkflowExecutionPort
from workflow.node_state import NodeStatus
from workflow.prompt_runtime import ContextItem


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
            request=_placeholder_request(request),
            audit_context=_audit_context(execution, self._actor.user_id),
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
        materials = self._definitions.resolve_materials(node_run_id)
        binding = materials.definition.node_binding
        context_items = self._context_items(execution, binding)
        upstream = self._upstream_artifacts(execution, binding)
        model_request_id = self._attempts.next_model_request_id(node_run_id)
        compiled = compile_node_prompt(
            definition=materials.definition,
            execution=execution,
            prompt_template=materials.prompt_template,
            output_schema=materials.output_schema,
            context_items=context_items,
            request_id=model_request_id,
            user_id=self._actor.user_id,
        )
        snapshots = self._snapshots.freeze(
            node_run_id,
            context=compiled.context,
            prompt=compiled.prompt,
        )
        runtime_values: dict[str, Any] = {}
        target_auth = self._assets.authorize_target_slots(materials.definition, execution)
        newly_frozen = self._workflow.freeze_execution(
            execution,
            request_id=request_id,
            snapshot=_execution_snapshot(execution, compiled, snapshots, upstream),
        )
        if not newly_frozen and execution.status == NodeStatus.RUNNING.value:
            if self._attempts.has_active_attempt(node_run_id):
                raise NodeExecutionError(
                    "NODE_EXECUTION_IN_FLIGHT",
                    "another worker already owns the frozen node execution",
                )
        self._workflow.start(node_run_id)
        return PreparedNodeExecution(
            node_run_id=node_run_id,
            request=compiled.request,
            audit_context=compiled.audit_context,
            output_schema=materials.output_schema,
            commit_context=NodeExecutionCommitContext(
                definition=materials.definition,
                execution=execution,
                snapshots=snapshots,
                upstream_artifacts=upstream,
                runtime_values=runtime_values,
                target_slot_authorization=target_auth,
                reference_asset_authorization=None,
            ),
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
        self._workflow.terminalize(
            execution.node_run_id,
            code=code,
            cancelled=cancelled,
        )

    def _context_items(
        self,
        execution: WorkflowExecutionContext,
        binding: Mapping[str, Any],
    ) -> tuple[ContextItem, ...]:
        policy = cast(object, binding.get("context_policy"))
        if not isinstance(policy, Mapping):
            raise NodeExecutionError(
                "NODE_EXECUTION_CONTEXT_POLICY_INVALID",
                "the published context policy is invalid",
            )
        typed_policy = cast(Mapping[str, Any], policy)
        allowed = cast(object, typed_policy.get("allowed_sources"))
        if not isinstance(allowed, Sequence) or isinstance(allowed, (str, bytes, bytearray)):
            raise NodeExecutionError(
                "NODE_EXECUTION_CONTEXT_POLICY_INVALID",
                "the published context policy has no source allowlist",
            )
        items: list[ContextItem] = []
        for source in cast(Sequence[object], allowed):
            if type(source) is not str:
                raise NodeExecutionError(
                    "NODE_EXECUTION_CONTEXT_POLICY_INVALID",
                    "the published context source is invalid",
                )
            for value in self._artifacts.list_context_versions(execution.project_id, source):
                items.append(
                    ContextItem(
                        source=source,
                        source_id=str(value.artifact_version_id),
                        source_version_id=str(value.artifact_version_id),
                        content=value.content,
                    )
                )
            for value in self._assets.list_context_items(execution.project_id, source):
                items.append(_asset_context_item(source, value))
        return tuple(items)

    def _upstream_artifacts(
        self,
        execution: WorkflowExecutionContext,
        binding: Mapping[str, Any],
    ) -> dict[str, ArtifactContextVersion]:
        refs = binding.get("input_contract_refs")
        if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes, bytearray)):
            raise NodeExecutionError(
                "NODE_EXECUTION_INPUT_CONTRACT_INVALID",
                "the published input contract list is invalid",
            )
        upstream: dict[str, ArtifactContextVersion] = {}
        for raw in cast(Sequence[object], refs):
            if type(raw) is not str:
                continue
            values = self._artifacts.list_context_versions(execution.project_id, raw)
            if len(values) == 1:
                upstream[raw] = values[0]
        return upstream


def _asset_context_item(source: str, value: AssetContextItem) -> ContextItem:
    return ContextItem(
        source=source,
        source_id=str(value.source_id),
        source_version_id=str(value.source_version_id),
        content=value.facts,
    )


def _execution_snapshot(
    execution: WorkflowExecutionContext,
    compiled: CompiledNodePrompt,
    snapshots: FrozenSnapshotRefs,
    upstream: Mapping[str, ArtifactContextVersion],
) -> dict[str, Any]:
    return {
        "content_release_id": str(execution.content_release_id),
        "workflow_definition_version_id": str(execution.workflow_definition_version_id),
        "node_key": execution.node_key,
        "context_hash": snapshots.context_hash,
        "prompt_hash": snapshots.prompt_hash,
        "context": list(compiled.context.bindings),
        "upstream_artifacts": {
            key: str(value.artifact_version_id) for key, value in upstream.items()
        },
    }


def _audit_context(execution: WorkflowExecutionContext, user_id: UUID | None) -> ModelAuditContext:
    return ModelAuditContext(
        organization_id=execution.organization_id,
        user_id=user_id,
        project_id=execution.project_id,
        node_run_id=execution.node_run_id,
        generation_job_id=None,
    )


def _placeholder_request(request_id: str) -> TextModelRequest:
    return TextModelRequest(
        capability=ModelCapability.TEXT_SMOKE,
        request_id=f"node-execution:committed:{request_id}"[:160],
        prompt="committed node execution",
    )


def _ignore_fault_stage(_stage: str) -> None:
    return None
