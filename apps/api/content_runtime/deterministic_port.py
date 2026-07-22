"""Published deterministic-output facts for internal runtime executors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageVersion,
    ContentRelease,
    ContentReleaseItem,
)
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.runtime_boundary.ports import WorkflowExecutionContext
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY


class DeterministicDefinitionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DeterministicNodeDefinition:
    content_release_id: UUID
    workflow_definition_version_id: UUID
    node_key: str
    execution_scope: str
    branch_key: str
    executor_ref: str
    input_contract_refs: tuple[str, ...]
    output_contract_refs: tuple[str, ...]
    node_binding: Mapping[str, Any]
    content_definition_version_id: UUID
    content_definition_key: str
    output_schema: Mapping[str, Any]


class DeterministicWorkflowFactsReader(Protocol):
    def require_context(
        self,
        node_run_id: UUID,
        *,
        for_update: bool,
    ) -> WorkflowExecutionContext: ...

    def published_graph(self, workflow_definition_version_id: UUID) -> Mapping[str, Any]: ...


class SqlAlchemyDeterministicDefinitionReader:
    """Resolve one deterministic executor only from a project's fixed release."""

    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        workflow: DeterministicWorkflowFactsReader,
    ) -> None:
        self._session = session
        self._actor = actor
        self._workflow = workflow

    def resolve(self, node_run_id: UUID) -> DeterministicNodeDefinition:
        execution = self._workflow.require_context(node_run_id, for_update=False)
        ProjectAccessService(self._session, self._actor).require(
            execution.project_id,
            ProjectAction.GENERATE,
        )
        release = self._session.scalar(
            select(ContentRelease).where(
                ContentRelease.id == execution.content_release_id,
                ContentRelease.status == "published",
            )
        )
        if release is None:
            raise _error(
                "PPT_RUNTIME_RELEASE_UNPUBLISHED",
                "the fixed content release is not published",
            )
        graph = self._workflow.published_graph(execution.workflow_definition_version_id)
        try:
            registered = BUILTIN_WORKFLOW_REGISTRY.load(dict(graph))
            registered.require_output_projection()
        except Exception as exc:
            raise _error(
                getattr(exc, "code", "PPT_RUNTIME_WORKFLOW_UNSUPPORTED"),
                "the fixed workflow cannot drive deterministic output persistence",
            ) from exc
        node = registered.node_by_key.get(execution.node_key)
        if node is None or node.execution_kind != "deterministic":
            raise _error(
                "PPT_RUNTIME_EXECUTION_KIND_INVALID",
                "the node is not a published deterministic executor",
            )
        executor_ref = node.binding.get("executor_ref")
        if type(executor_ref) is not str or not executor_ref:
            raise _error(
                "PPT_RUNTIME_EXECUTOR_UNDECLARED",
                "the deterministic node has no fixed executor",
            )
        output_bindings = [
            value
            for value in registered.output_definition_index.values()
            if value.producer_node_key == execution.node_key
        ]
        if len(output_bindings) != 1:
            raise _error(
                "PPT_RUNTIME_OUTPUT_DEFINITION_INVALID",
                "the deterministic node must resolve exactly one output definition",
            )
        output = output_bindings[0]
        package_ids = tuple(
            self._session.scalars(
                select(ContentReleaseItem.content_package_version_id)
                .join(
                    ContentPackageVersion,
                    ContentPackageVersion.id == ContentReleaseItem.content_package_version_id,
                )
                .where(
                    ContentReleaseItem.content_release_id == release.id,
                    ContentPackageVersion.status == "published",
                )
            )
        )
        definitions = list(
            self._session.scalars(
                select(ContentDefinitionVersion).where(
                    ContentDefinitionVersion.content_package_version_id.in_(package_ids),
                    ContentDefinitionVersion.definition_key == output.content_definition_key,
                )
            )
        )
        if len(definitions) != 1:
            raise _error(
                "PPT_RUNTIME_OUTPUT_DEFINITION_INVALID",
                "the fixed deterministic output definition is missing or ambiguous",
            )
        definition = definitions[0]
        if (
            output.generation_template_key is not None
            or node.branch_key is None
            or output.producer_branch_key != node.branch_key
            or output.execution_scope != node.execution_scope
        ):
            raise _error(
                "PPT_RUNTIME_OUTPUT_DEFINITION_INVALID",
                "the deterministic output definition disagrees with its producer",
            )
        return DeterministicNodeDefinition(
            content_release_id=release.id,
            workflow_definition_version_id=execution.workflow_definition_version_id,
            node_key=execution.node_key,
            execution_scope=node.execution_scope,
            branch_key=node.branch_key,
            executor_ref=executor_ref,
            input_contract_refs=tuple(node.input_contract_refs),
            output_contract_refs=tuple(node.output_contract_refs),
            node_binding=node.binding,
            content_definition_version_id=definition.id,
            content_definition_key=definition.definition_key,
            output_schema=cast(Mapping[str, Any], definition.schema_json),
        )


def _error(code: str, message: str) -> DeterministicDefinitionError:
    return DeterministicDefinitionError(code, message)
