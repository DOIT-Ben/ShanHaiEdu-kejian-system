"""Application guard for the trusted generated Artifact write capability."""

from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.artifacts.execution_errors import ArtifactExecutionPortError
from apps.api.content_runtime.authoring_policy import AuthoringPolicyUnavailable
from apps.api.content_runtime.authoring_policy_loader import AuthoringPolicyLoader
from apps.api.content_runtime.runtime_port import (
    RuntimeDefinitionError,
    SqlAlchemyRuntimeDefinitionReader,
)
from apps.api.identity.context import ActorContext
from apps.api.model_gateway.execution_port import (
    AttemptExecutionPortError,
    SqlAlchemyAttemptExecutionPort,
)
from apps.api.prompt_runtime.execution_port import SqlAlchemyPromptSnapshotPort
from apps.api.prompt_runtime.service import PromptSnapshotError
from apps.api.runtime_boundary.ports import (
    GeneratedArtifactWrite,
    RuntimeNodeDefinition,
    WorkflowExecutionContext,
)
from apps.api.runtime_boundary.projection_artifact import compile_artifact_identity
from apps.api.runtime_boundary.projection_values import (
    OutputProjectionError,
    require_mapping,
)
from apps.api.workflows.execution_port import (
    SqlAlchemyWorkflowExecutionPort,
    WorkflowExecutionPortError,
)
from workflow.node_state import NodeStatus


class GeneratedArtifactWriteGuard:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require(self, write: GeneratedArtifactWrite) -> None:
        workflow = SqlAlchemyWorkflowExecutionPort(self._session, self._actor)
        try:
            execution = workflow.require_context(write.node_run_id, for_update=False)
            definition = SqlAlchemyRuntimeDefinitionReader(
                self._session,
                self._actor,
                workflow,
            ).resolve(write.node_run_id)
            snapshots = SqlAlchemyPromptSnapshotPort(
                self._session,
                self._actor,
            ).load_frozen(write.node_run_id)
            SqlAlchemyAttemptExecutionPort(self._session, self._actor).require_succeeded(
                node_run_id=write.node_run_id,
                project_id=write.project_id,
                request_id=write.request_id,
            )
            artifact_key, artifact_type, branch_key = self._artifact_identity(
                definition,
                execution,
            )
        except (
            AttemptExecutionPortError,
            OutputProjectionError,
            PromptSnapshotError,
            RuntimeDefinitionError,
            WorkflowExecutionPortError,
        ) as exc:
            raise self._provenance_error() from exc

        if (
            execution.status != NodeStatus.RUNNING.value
            or execution.project_id != write.project_id
            or execution.lesson_unit_id != write.lesson_unit_id
            or definition.content_release_id != execution.content_release_id
            or definition.workflow_definition_version_id != execution.workflow_definition_version_id
            or definition.node_key != execution.node_key
            or definition.content_definition_version_id != write.content_definition_version_id
            or snapshots.context_snapshot_id != write.context_snapshot_id
            or snapshots.prompt_snapshot_id != write.prompt_snapshot_id
            or artifact_key != write.artifact_key
            or artifact_type != write.artifact_type
            or branch_key != write.branch_key
        ):
            raise self._provenance_error()

        try:
            AuthoringPolicyLoader(self._session).require_by_id(
                definition.content_definition_version_id
            )
        except AuthoringPolicyUnavailable as exc:
            raise ArtifactExecutionPortError(
                "AUTHORING_POLICY_UNAVAILABLE",
                "the generated artifact definition has no published authoring policy",
            ) from exc

    @staticmethod
    def _artifact_identity(
        definition: RuntimeNodeDefinition,
        execution: WorkflowExecutionContext,
    ) -> tuple[str, str, str]:
        binding = require_mapping(definition.node_binding, "NODE_BINDING_INVALID")
        persistence = require_mapping(
            binding.get("output_persistence"),
            "OUTPUT_PROJECTION_DECLARATION_MISSING",
        )
        artifact = require_mapping(
            persistence.get("artifact"),
            "OUTPUT_PROJECTION_ARTIFACT_DECLARATION_INVALID",
        )
        return compile_artifact_identity(
            definition=definition,
            execution=execution,
            binding=binding,
            artifact=artifact,
        )

    @staticmethod
    def _provenance_error() -> ArtifactExecutionPortError:
        return ArtifactExecutionPortError(
            "NODE_EXECUTION_ARTIFACT_PROVENANCE_INVALID",
            "the generated artifact write does not match its frozen execution",
        )
