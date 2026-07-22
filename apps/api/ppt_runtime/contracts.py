"""ORM-free contracts for deterministic PPT node execution."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from apps.api.assets.ppt_runtime_contracts import PptBackgroundFact, PublishedPptxObject
from apps.api.content_runtime.deterministic_port import DeterministicNodeDefinition
from apps.api.model_gateway.deterministic_port import DeterministicAttemptLease
from apps.api.ppt_rendering import AssemblyManifest, ManifestPage, PptxFileFact
from apps.api.runtime_boundary.ports import ArtifactContextVersion, WorkflowExecutionContext


class PptRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class PptRuntimeResult:
    node_run_id: UUID
    artifact_version_id: UUID
    file_asset_version_id: UUID | None
    attempt_id: UUID
    usage_id: UUID


@dataclass(frozen=True, slots=True)
class PreparedPptRuntime:
    definition: DeterministicNodeDefinition
    execution: WorkflowExecutionContext
    request_id: str
    request_hash: str
    owner_token: str
    attempt: DeterministicAttemptLease
    upstream_artifacts: Mapping[str, ArtifactContextVersion]
    page_spec_version_id: UUID
    page_spec_content: Mapping[str, Any]
    backgrounds: tuple[PptBackgroundFact, ...]
    recovered_pages: tuple[ManifestPage, ...] = ()
    assembly_artifact_version_id: UUID | None = None
    assembly_content: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PptRenderProduct:
    manifest: AssemblyManifest
    pptx: PptxFileFact | None


class PptRuntimeTransaction(Protocol):
    def prepare(
        self,
        node_run_id: UUID,
        request_id: str,
    ) -> PreparedPptRuntime | PptRuntimeResult: ...

    def complete(
        self,
        prepared: PreparedPptRuntime,
        product: PptRenderProduct,
        published: PublishedPptxObject | None,
        *,
        latency_ms: int,
    ) -> PptRuntimeResult: ...

    def terminalize_failure(
        self,
        prepared: PreparedPptRuntime,
        *,
        code: str,
        cancelled: bool,
        latency_ms: int,
        completed_pages: tuple[ManifestPage, ...],
    ) -> None: ...

    def fail_prepare(self, node_run_id: UUID, *, code: str) -> None: ...


class PptRuntimeTransactionFactory(Protocol):
    def begin(self) -> AbstractContextManager[PptRuntimeTransaction]: ...
