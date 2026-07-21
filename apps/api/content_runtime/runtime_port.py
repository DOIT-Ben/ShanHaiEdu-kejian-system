"""Published runtime definition lookup for the generic node executor."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageItemVersion,
    ContentRelease,
    ContentReleaseItem,
)
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.runtime_boundary.ports import RuntimeNodeDefinition, WorkflowExecutionContext
from workflow.definition import WorkflowNodeDefinition
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY


class RuntimeDefinitionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class RuntimeNodeMaterials:
    definition: RuntimeNodeDefinition
    prompt_template: Mapping[str, Any]
    output_schema: dict[str, Any]


class WorkflowFactsReader(Protocol):
    def require_context(
        self, node_run_id: UUID, *, for_update: bool
    ) -> WorkflowExecutionContext: ...

    def published_graph(self, workflow_definition_version_id: UUID) -> Mapping[str, Any]: ...


class SqlAlchemyRuntimeDefinitionReader:
    """Resolve only immutable, published facts visible to the current tenant."""

    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        workflow: WorkflowFactsReader,
    ) -> None:
        self._session = session
        self._actor = actor
        self._workflow = workflow

    def resolve(self, node_run_id: UUID) -> RuntimeNodeDefinition:
        return self.resolve_materials(node_run_id).definition

    def resolve_materials(self, node_run_id: UUID) -> RuntimeNodeMaterials:
        execution = self._workflow.require_context(node_run_id, for_update=False)
        ProjectAccessService(self._session, self._actor).require(
            execution.project_id,
            ProjectAction.GENERATE,
        )
        release = self._require_release(execution.content_release_id)
        graph = self._workflow.published_graph(execution.workflow_definition_version_id)
        node = self._registered_node(execution, graph)
        binding = node.binding
        template_key = _reference_key(binding, "generation_template_ref")
        package_ids = self._package_ids(release.id)
        template = self._package_item(package_ids, template_key, "generation_template")
        spec = _mapping(template.get("spec"))
        output_key = _reference_key(spec, "output_definition_ref")
        content_definition = self._content_definition(package_ids, output_key)
        definition = RuntimeNodeDefinition(
            content_release_id=release.id,
            workflow_definition_version_id=execution.workflow_definition_version_id,
            node_key=execution.node_key,
            execution_kind=node.execution_kind,
            generation_template_key=template_key,
            generation_template=template,
            node_binding=binding,
            content_definition_version_id=content_definition.id,
            content_definition_release_id=release.id,
            content_definition_item_key=output_key,
        )
        prompt_key = _reference_key(spec, "prompt_template_ref")
        prompt = self._package_item(package_ids, prompt_key, "prompt_template")
        return RuntimeNodeMaterials(
            definition=definition,
            prompt_template=prompt,
            output_schema=content_definition.schema_json,
        )

    def _require_release(self, release_id: UUID) -> ContentRelease:
        release = self._session.scalar(
            select(ContentRelease).where(
                ContentRelease.id == release_id,
                ContentRelease.status == "published",
            )
        )
        if release is None:
            raise RuntimeDefinitionError(
                "NODE_EXECUTION_RELEASE_UNPUBLISHED",
                "the fixed content release is not published",
            )
        return release

    @staticmethod
    def _registered_node(
        execution: WorkflowExecutionContext,
        graph: Mapping[str, Any],
    ) -> WorkflowNodeDefinition:
        try:
            registered = BUILTIN_WORKFLOW_REGISTRY.load(dict(graph))
            registered.require_output_projection()
        except Exception as exc:
            raise RuntimeDefinitionError(
                getattr(exc, "code", "WORKFLOW_RELEASE_UNSUPPORTED"),
                str(exc),
            ) from exc
        node = registered.node_by_key.get(execution.node_key)
        if node is None:
            raise RuntimeDefinitionError(
                "NODE_EXECUTION_NODE_UNDECLARED",
                "the node run key is absent from the published workflow",
            )
        if node.execution_kind != "model_generation":
            raise RuntimeDefinitionError(
                "NODE_EXECUTION_KIND_UNSUPPORTED",
                "the generic executor only accepts model-generation nodes",
            )
        return node

    def _package_ids(self, release_id: UUID) -> tuple[UUID, ...]:
        values = tuple(
            self._session.scalars(
                select(ContentReleaseItem.content_package_version_id).where(
                    ContentReleaseItem.content_release_id == release_id,
                )
            )
        )
        if not values:
            raise RuntimeDefinitionError(
                "NODE_EXECUTION_RELEASE_ITEMS_MISSING",
                "the published release has no mounted package",
            )
        return values

    def _package_item(
        self,
        package_ids: tuple[UUID, ...],
        item_key: str,
        kind: str,
    ) -> dict[str, Any]:
        rows = list(
            self._session.scalars(
                select(ContentPackageItemVersion).where(
                    ContentPackageItemVersion.content_package_version_id.in_(package_ids),
                    ContentPackageItemVersion.item_key == item_key,
                    ContentPackageItemVersion.kind == kind,
                )
            )
        )
        if len(rows) != 1:
            raise RuntimeDefinitionError(
                "NODE_EXECUTION_RELEASE_ITEM_AMBIGUOUS",
                f"the published {kind} is missing or ambiguous",
            )
        return rows[0].payload_json

    def _content_definition(
        self,
        package_ids: tuple[UUID, ...],
        definition_key: str,
    ) -> ContentDefinitionVersion:
        rows = list(
            self._session.scalars(
                select(ContentDefinitionVersion).where(
                    ContentDefinitionVersion.content_package_version_id.in_(package_ids),
                    ContentDefinitionVersion.definition_key == definition_key,
                )
            )
        )
        if len(rows) != 1:
            raise RuntimeDefinitionError(
                "NODE_EXECUTION_OUTPUT_DEFINITION_AMBIGUOUS",
                "the published output definition is missing or ambiguous",
            )
        return rows[0]


def _reference_key(value: Mapping[str, Any], field: str) -> str:
    reference = _mapping(value.get(field))
    return _text(reference.get("item_key"), f"{field} item key")


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeDefinitionError(
            "NODE_EXECUTION_RELEASE_CONTRACT_INVALID",
            "published runtime contract requires an object",
        )
    return cast(Mapping[str, Any], value)


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise RuntimeDefinitionError(
            "NODE_EXECUTION_RELEASE_CONTRACT_INVALID",
            f"published runtime contract requires a {label}",
        )
    return value
