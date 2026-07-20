"""Minimal ORM-free application ports required by Issue #89."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol, cast
from uuid import UUID

from apps.api.artifacts.domain import (
    ArtifactImpactScope,
    ArtifactInvariantError,
    ArtifactRelationType,
)
from apps.api.model_gateway.contracts import (
    ModelAuditContext,
    TextGatewayResult,
    TextModelRequest,
)
from apps.api.model_gateway.ports import CancellationToken
from workflow.node_state import NodeStatus
from workflow.prompt_runtime import AssembledContext, CompiledPrompt


@dataclass(frozen=True, slots=True)
class RuntimeNodeDefinition:
    content_release_id: UUID
    workflow_definition_version_id: UUID
    node_key: str
    execution_kind: str
    generation_template_key: str
    generation_template: Mapping[str, Any]
    node_binding: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class WorkflowExecutionContext:
    organization_id: UUID
    project_id: UUID
    workflow_run_id: UUID
    node_run_id: UUID
    content_release_id: UUID
    workflow_definition_version_id: UUID
    node_key: str
    status: str


@dataclass(frozen=True, slots=True)
class ArtifactContextVersion:
    artifact_version_id: UUID
    artifact_type: str
    content: Mapping[str, Any]
    content_hash: str


@dataclass(frozen=True, slots=True)
class AssetContextItem:
    source_id: UUID
    source_version_id: UUID
    media_type: str
    content_hash: str
    facts: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class GeneratedArtifactRelation:
    from_artifact_version_id: UUID
    relation_type: ArtifactRelationType
    binding_key: str
    impact_scope: Mapping[str, Any]

    def __post_init__(self) -> None:
        raw_source_id = cast(object, self.from_artifact_version_id)
        if not isinstance(raw_source_id, UUID):
            raise ArtifactInvariantError("generated relation source version is invalid")
        raw_relation_type: object = self.relation_type
        if type(raw_relation_type) is not ArtifactRelationType:
            raise ArtifactInvariantError("generated relation type is invalid")
        raw_binding_key: object = self.binding_key
        if (
            type(raw_binding_key) is not str
            or not raw_binding_key.strip()
            or len(raw_binding_key) > 160
        ):
            raise ArtifactInvariantError("generated relation binding_key is invalid")
        scope = ArtifactImpactScope.from_mapping(self.impact_scope)
        canonical: dict[str, Any] = {"mode": scope.mode}
        if scope.mode == "keyed":
            assert scope.selector is not None
            canonical.update(selector=scope.selector.value, keys=scope.keys)
        object.__setattr__(self, "impact_scope", MappingProxyType(canonical))


@dataclass(frozen=True, slots=True)
class GeneratedArtifactWrite:
    project_id: UUID
    node_run_id: UUID
    context_snapshot_id: UUID
    prompt_snapshot_id: UUID
    artifact_key: str
    artifact_type: str
    branch_key: str
    content_definition_version_id: UUID
    content: Mapping[str, Any]
    request_id: str
    relations: tuple[GeneratedArtifactRelation, ...] = ()

    def __post_init__(self) -> None:
        relations: tuple[object, ...] = tuple(self.relations)
        if any(type(item) is not GeneratedArtifactRelation for item in relations):
            raise ArtifactInvariantError("generated artifact relations are invalid")
        object.__setattr__(self, "relations", relations)


@dataclass(frozen=True, slots=True)
class ArtifactWriteResult:
    artifact_id: UUID
    artifact_version_id: UUID
    content_hash: str


@dataclass(frozen=True, slots=True)
class FrozenSnapshotRefs:
    context_snapshot_id: UUID
    prompt_snapshot_id: UUID
    context_hash: str
    prompt_hash: str


@dataclass(frozen=True, slots=True)
class CreationPackageSpec:
    project_id: UUID
    workflow_run_id: UUID
    node_run_id: UUID
    artifact_version_id: UUID
    target_slots: tuple[str, ...]
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CreationPackageWriteResult:
    creation_package_id: UUID
    status: str
    content_hash: str


class RuntimeDefinitionReader(Protocol):
    def resolve(self, node_run_id: UUID) -> RuntimeNodeDefinition: ...


class WorkflowExecutionPort(Protocol):
    def require_context(
        self, node_run_id: UUID, *, for_update: bool
    ) -> WorkflowExecutionContext: ...

    def transition(self, node_run_id: UUID, target: NodeStatus) -> None: ...


class ArtifactPort(Protocol):
    def list_context_versions(
        self, project_id: UUID, source: str
    ) -> tuple[ArtifactContextVersion, ...]: ...

    def persist_generated(self, write: GeneratedArtifactWrite) -> ArtifactWriteResult: ...


class AssetPort(Protocol):
    def list_context_items(self, project_id: UUID, source: str) -> tuple[AssetContextItem, ...]: ...


class PromptSnapshotPort(Protocol):
    def freeze(
        self,
        node_run_id: UUID,
        *,
        context: AssembledContext,
        prompt: CompiledPrompt,
    ) -> FrozenSnapshotRefs: ...


class ModelInvocationPort(Protocol):
    async def generate_text(
        self,
        request: TextModelRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> TextGatewayResult: ...


class CreationPackagePort(Protocol):
    def publish(self, spec: CreationPackageSpec) -> CreationPackageWriteResult: ...
