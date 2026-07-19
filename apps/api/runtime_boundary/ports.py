"""Minimal ORM-free application ports required by Issue #89."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


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

    def transition(self, node_run_id: UUID, target: str) -> None: ...


class ArtifactPort(Protocol):
    def list_context_versions(
        self, project_id: UUID, source: str
    ) -> tuple[ArtifactContextVersion, ...]: ...

    def persist_generated(self, write: GeneratedArtifactWrite) -> ArtifactWriteResult: ...


class AssetPort(Protocol):
    def list_context_items(
        self, project_id: UUID, source: str
    ) -> tuple[AssetContextItem, ...]: ...


class PromptSnapshotPort(Protocol):
    def freeze(
        self,
        node_run_id: UUID,
        *,
        context: object,
        prompt: object,
    ) -> FrozenSnapshotRefs: ...


class ModelInvocationPort(Protocol):
    async def generate_text(
        self,
        request: object,
        *,
        cancellation: object | None = None,
        audit_context: object | None = None,
    ) -> object: ...


class CreationPackagePort(Protocol):
    def publish(self, spec: CreationPackageSpec) -> CreationPackageWriteResult: ...
