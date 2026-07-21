"""Minimal ORM-free application ports required by Issue #89."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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
from apps.api.runtime_boundary.contract_values import (
    freeze_json_value as _freeze_json_value,
)
from apps.api.runtime_boundary.contract_values import (
    require_content_hash as _require_content_hash,
)
from apps.api.runtime_boundary.contract_values import (
    require_text as _require_text,
)
from apps.api.runtime_boundary.contract_values import (
    require_uuid as _require_uuid,
)
from apps.api.runtime_boundary.contract_values import (
    require_uuid_fields as _require_uuid_fields,
)
from apps.api.runtime_boundary.creation_package_contracts import (
    CreationPackageItemSpec,
    CreationPackageReferenceAssetSpec,
    CreationPackageSpec,
    CreationPackageWriteResult,
    ReferenceAssetAuthorization,
    TargetSlotAuthorization,
)
from workflow.node_state import NodeStatus
from workflow.prompt_runtime import AssembledContext, CompiledPrompt

__all__ = (
    "ArtifactContextVersion",
    "ArtifactPort",
    "ArtifactWriteResult",
    "AssetContextItem",
    "AssetPort",
    "CreationPackageItemSpec",
    "CreationPackagePort",
    "CreationPackageReferenceAssetSpec",
    "CreationPackageSpec",
    "CreationPackageWriteResult",
    "FrozenSnapshotRefs",
    "GeneratedArtifactRelation",
    "GeneratedArtifactWrite",
    "ModelInvocationPort",
    "PromptSnapshotPort",
    "ReferenceAssetAuthorization",
    "RuntimeDefinitionReader",
    "RuntimeNodeDefinition",
    "TargetSlotAuthorization",
    "WorkflowExecutionContext",
    "WorkflowExecutionPort",
)


@dataclass(frozen=True, slots=True)
class RuntimeNodeDefinition:
    content_release_id: UUID
    workflow_definition_version_id: UUID
    node_key: str
    execution_kind: str
    generation_template_key: str
    generation_template: Mapping[str, Any]
    node_binding: Mapping[str, Any]
    content_definition_version_id: UUID
    content_definition_release_id: UUID | None = None
    content_definition_item_key: str | None = None

    def __post_init__(self) -> None:
        _require_uuid_fields(
            (self.content_release_id, "content release is invalid"),
            (self.workflow_definition_version_id, "workflow definition version is invalid"),
            (self.content_definition_version_id, "content definition version is invalid"),
        )
        if self.content_definition_release_id is not None:
            _require_uuid(
                self.content_definition_release_id,
                "content definition release is invalid",
            )
        for value, message in (
            (self.node_key, "runtime node key is invalid"),
            (self.execution_kind, "runtime execution kind is invalid"),
            (self.generation_template_key, "generation template key is invalid"),
        ):
            _require_text(value, message, 160)
        raw_template = cast(object, self.generation_template)
        raw_binding = cast(object, self.node_binding)
        if not isinstance(raw_template, Mapping) or not isinstance(raw_binding, Mapping):
            raise ArtifactInvariantError("runtime definition snapshots are invalid")
        object.__setattr__(
            self,
            "generation_template",
            _freeze_json_value(self.generation_template),
        )
        object.__setattr__(self, "node_binding", _freeze_json_value(self.node_binding))


@dataclass(frozen=True, slots=True)
class WorkflowExecutionContext:
    organization_id: UUID
    project_id: UUID
    workflow_run_id: UUID
    node_run_id: UUID
    content_release_id: UUID
    workflow_definition_version_id: UUID
    node_key: str
    branch_key: str | None
    lesson_key: str | None
    lesson_unit_id: UUID | None
    status: str


@dataclass(frozen=True, slots=True)
class ArtifactContextVersion:
    project_id: UUID
    lesson_unit_id: UUID | None
    artifact_version_id: UUID
    contract_ref: str
    artifact_type: str
    content: Mapping[str, Any]
    content_hash: str

    def __post_init__(self) -> None:
        _require_uuid_fields(
            (self.project_id, "artifact context project is invalid"),
            (self.artifact_version_id, "artifact context version is invalid"),
        )
        if self.lesson_unit_id is not None:
            _require_uuid(self.lesson_unit_id, "artifact context lesson unit is invalid")
        _require_text(self.contract_ref, "artifact context contract ref is invalid", 160)
        _require_text(self.artifact_type, "artifact context type is invalid", 80)
        raw_content = cast(object, self.content)
        if not isinstance(raw_content, Mapping):
            raise ArtifactInvariantError("artifact context content is invalid")
        _require_content_hash(self.content_hash, "artifact context hash is invalid")
        object.__setattr__(self, "content", _freeze_json_value(self.content))


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
        _require_text(self.binding_key, "generated relation binding_key is invalid", 160)
        scope = ArtifactImpactScope.from_mapping(self.impact_scope)
        canonical: dict[str, Any] = {"mode": scope.mode}
        if scope.mode == "keyed":
            assert scope.selector is not None
            canonical.update(selector=scope.selector.value, keys=scope.keys)
        object.__setattr__(self, "impact_scope", _freeze_json_value(canonical))


@dataclass(frozen=True, slots=True)
class GeneratedArtifactWrite:
    project_id: UUID
    lesson_unit_id: UUID | None
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
        _require_uuid_fields(
            (self.project_id, "generated artifact project is invalid"),
            (self.node_run_id, "generated artifact node run is invalid"),
            (self.context_snapshot_id, "generated artifact context snapshot is invalid"),
            (self.prompt_snapshot_id, "generated artifact prompt snapshot is invalid"),
            (
                self.content_definition_version_id,
                "generated artifact content definition is invalid",
            ),
        )
        if self.lesson_unit_id is not None:
            _require_uuid(self.lesson_unit_id, "generated artifact lesson unit is invalid")
        _require_text(self.artifact_key, "generated artifact key is invalid", 160)
        _require_text(self.artifact_type, "generated artifact type is invalid", 80)
        _require_text(self.branch_key, "generated artifact branch is invalid", 80)
        _require_text(self.request_id, "generated artifact request ID is invalid", 256)
        raw_content = cast(object, self.content)
        if not isinstance(raw_content, Mapping):
            raise ArtifactInvariantError("generated artifact content is invalid")
        relations: tuple[object, ...] = tuple(self.relations)
        if any(type(item) is not GeneratedArtifactRelation for item in relations):
            raise ArtifactInvariantError("generated artifact relations are invalid")
        object.__setattr__(self, "relations", relations)
        object.__setattr__(self, "content", _freeze_json_value(self.content))


@dataclass(frozen=True, slots=True)
class ArtifactWriteResult:
    artifact_id: UUID
    artifact_version_id: UUID
    content_hash: str
    project_id: UUID
    node_run_id: UUID
    context_snapshot_id: UUID
    prompt_snapshot_id: UUID
    artifact_key: str
    artifact_type: str
    branch_key: str
    lesson_unit_id: UUID | None
    content_definition_version_id: UUID

    def __post_init__(self) -> None:
        _require_uuid_fields(
            (self.artifact_id, "artifact write result artifact is invalid"),
            (self.artifact_version_id, "artifact write result version is invalid"),
            (self.project_id, "artifact write result project is invalid"),
            (self.node_run_id, "artifact write result node run is invalid"),
            (self.context_snapshot_id, "artifact write result context snapshot is invalid"),
            (self.prompt_snapshot_id, "artifact write result prompt snapshot is invalid"),
            (
                self.content_definition_version_id,
                "artifact write result content definition is invalid",
            ),
        )
        if self.lesson_unit_id is not None:
            _require_uuid(self.lesson_unit_id, "artifact write result lesson unit is invalid")
        _require_text(self.artifact_key, "artifact write result artifact key is invalid", 160)
        _require_text(self.artifact_type, "artifact write result artifact type is invalid", 80)
        _require_text(self.branch_key, "artifact write result branch is invalid", 80)
        _require_content_hash(self.content_hash, "artifact write result content hash is invalid")


@dataclass(frozen=True, slots=True)
class FrozenSnapshotRefs:
    context_snapshot_id: UUID
    prompt_snapshot_id: UUID
    context_hash: str
    prompt_hash: str

    def __post_init__(self) -> None:
        _require_uuid_fields(
            (self.context_snapshot_id, "context snapshot is invalid"),
            (self.prompt_snapshot_id, "prompt snapshot is invalid"),
        )


class RuntimeDefinitionReader(Protocol):
    def resolve(self, node_run_id: UUID) -> RuntimeNodeDefinition: ...


class WorkflowExecutionPort(Protocol):
    def require_context(
        self, node_run_id: UUID, *, for_update: bool
    ) -> WorkflowExecutionContext: ...

    def transition(self, node_run_id: UUID, target: NodeStatus) -> None: ...

    def claim_execution_owner(self, node_run_id: UUID, owner_token: str) -> None: ...

    def owns_execution_owner(self, node_run_id: UUID, owner_token: str) -> bool: ...

    def release_execution_owner(self, node_run_id: UUID, owner_token: str) -> None: ...


class ArtifactPort(Protocol):
    def list_context_versions(
        self, execution: WorkflowExecutionContext, source: str
    ) -> tuple[ArtifactContextVersion, ...]: ...

    def verify_frozen_versions(
        self,
        execution: WorkflowExecutionContext,
        upstream: dict[str, ArtifactContextVersion],
    ) -> None: ...

    def persist_generated(self, write: GeneratedArtifactWrite) -> ArtifactWriteResult: ...


class AssetPort(Protocol):
    def list_context_items(self, project_id: UUID, source: str) -> tuple[AssetContextItem, ...]: ...

    def freeze_reference_assets(
        self,
        definition: RuntimeNodeDefinition,
        execution: WorkflowExecutionContext,
    ) -> ReferenceAssetAuthorization | None: ...


class PromptSnapshotPort(Protocol):
    def freeze(
        self,
        node_run_id: UUID,
        *,
        context: AssembledContext,
        prompt: CompiledPrompt,
    ) -> FrozenSnapshotRefs: ...

    def verify(self, refs: FrozenSnapshotRefs) -> None: ...


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
