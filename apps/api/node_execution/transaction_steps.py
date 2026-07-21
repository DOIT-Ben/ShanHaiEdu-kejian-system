"""Contained replay and output-persistence steps for the transaction owner."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from apps.api.artifacts.execution_port import SqlAlchemyArtifactPort
from apps.api.creation.execution_port import SqlAlchemyCreationPackagePort
from apps.api.model_gateway.execution_port import (
    AttemptEvidence,
    SqlAlchemyAttemptExecutionPort,
)
from apps.api.runtime_boundary.output_projection import compile_output_projection
from apps.api.runtime_boundary.ports import WorkflowExecutionContext
from apps.api.runtime_boundary.projection_package import materialize_creation_package
from apps.api.workflows.execution_port import SqlAlchemyWorkflowExecutionPort

from .contracts import (
    CommittedNodeExecution,
    NodeExecutionCommitContext,
    NodeExecutionError,
    PreparedNodeExecution,
)
from .materials import audit_context, placeholder_request
from .recovery import SqlAlchemyRecoveryFactStore


def claim_execution_owner(
    workflow: SqlAlchemyWorkflowExecutionPort,
    node_run_id: UUID,
) -> str:
    owner_token = str(uuid4())
    try:
        workflow.claim_execution_owner(node_run_id, owner_token)
    except Exception as exc:
        raise NodeExecutionError(
            getattr(exc, "code", "NODE_EXECUTION_IN_FLIGHT"),
            str(exc),
        ) from exc
    return owner_token


def terminalize_execution_failure(
    *,
    execution: PreparedNodeExecution,
    code: str,
    cancelled: bool,
    workflow: SqlAlchemyWorkflowExecutionPort,
    recovery: SqlAlchemyRecoveryFactStore,
) -> None:
    owner_token = execution.execution_owner_token
    if owner_token is not None:
        if not workflow.owns_execution_owner(execution.node_run_id, owner_token):
            return
        workflow.release_execution_owner(execution.node_run_id, owner_token)
    elif cancelled:
        workflow.clear_execution_owner(execution.node_run_id)
    if cancelled or code == "NODE_EXECUTION_RECOVERY_EXPIRED":
        recovery.discard(execution.node_run_id)
    workflow.terminalize(
        execution.node_run_id,
        code=code,
        cancelled=cancelled,
    )


def prepare_committed_execution(
    *,
    execution: WorkflowExecutionContext,
    committed_version_id: UUID,
    node_run_id: UUID,
    user_id: UUID | None,
    artifacts: SqlAlchemyArtifactPort,
    attempts: SqlAlchemyAttemptExecutionPort,
    packages: SqlAlchemyCreationPackagePort,
) -> PreparedNodeExecution:
    existing = artifacts.result_for_version(committed_version_id)
    request_id = artifacts.request_id_for_version(committed_version_id)
    evidence = attempts.require_succeeded(
        node_run_id=node_run_id,
        project_id=execution.project_id,
        request_id=request_id,
    )
    return PreparedNodeExecution(
        node_run_id=node_run_id,
        request=placeholder_request(request_id),
        audit_context=audit_context(execution, user_id),
        output_schema={},
        committed_result=CommittedNodeExecution(
            node_run_id=node_run_id,
            artifact_version_id=existing.artifact_version_id,
            creation_package_id=packages.find_for_node(node_run_id),
            attempt_id=evidence.attempt_id,
            usage_id=evidence.usage_id,
        ),
    )


def prepare_cancel_requested_execution(
    execution: WorkflowExecutionContext,
    request_id: str,
    user_id: UUID | None,
) -> PreparedNodeExecution:
    return PreparedNodeExecution(
        node_run_id=execution.node_run_id,
        request=placeholder_request(request_id),
        audit_context=audit_context(execution, user_id),
        output_schema={},
        pre_model_error_code="NODE_EXECUTION_CANCEL_REQUESTED",
        pre_model_error_message="the node run was cancelled before execution",
    )


def persist_execution_outputs(
    *,
    execution: PreparedNodeExecution,
    current: WorkflowExecutionContext,
    context: NodeExecutionCommitContext,
    output: dict[str, object],
    evidence: AttemptEvidence,
    owner_token: str,
    artifacts: SqlAlchemyArtifactPort,
    packages: SqlAlchemyCreationPackagePort,
    workflow: SqlAlchemyWorkflowExecutionPort,
    fault_injector: Callable[[str], None],
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
    artifact_result = artifacts.persist_generated(plan.artifact_write)
    fault_injector("after_artifact")
    package = materialize_creation_package(plan, artifact_result=artifact_result)
    package_result = packages.publish(package) if package is not None else None
    fault_injector("after_package")
    fault_injector("before_transition")
    workflow.release_execution_owner(execution.node_run_id, owner_token)
    workflow.complete(execution.node_run_id, artifact_result.artifact_version_id)
    return CommittedNodeExecution(
        node_run_id=execution.node_run_id,
        artifact_version_id=artifact_result.artifact_version_id,
        creation_package_id=(
            package_result.creation_package_id if package_result is not None else None
        ),
        attempt_id=evidence.attempt_id,
        usage_id=evidence.usage_id,
    )
