"""ORM-free contracts for the golden classroom-intro video runtime."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from apps.api.model_gateway.contracts import (
    GeneratedFileFact,
    MediaReference,
    ModelAuditContext,
    VideoGatewayResult,
    VideoModelRequest,
    VideoPollRequest,
)


class VideoRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class VideoRuntimeResult:
    node_run_id: UUID
    generation_job_id: UUID
    status: Literal["submitted", "processing", "completed"]
    generation_result_id: UUID | None
    file_asset_version_id: UUID | None


@dataclass(frozen=True, slots=True)
class PreparedVideoRuntime:
    node_run_id: UUID
    generation_job_id: UUID
    organization_id: UUID
    project_id: UUID
    lesson_unit_id: UUID
    creation_item_id: UUID
    audit_context: ModelAuditContext
    prompt: str
    keyframe: MediaReference
    duration_seconds: int
    provider_task_id: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedVideoFile:
    storage_bucket: str
    storage_key: str
    etag: str
    mime_type: str
    size_bytes: int
    sha256: str
    width: int
    height: int
    duration_ms: int


class VideoRuntimeTransaction(Protocol):
    def prepare_start(
        self,
        node_run_id: UUID,
        keyframe_file_version_id: UUID,
        request_id: str,
    ) -> PreparedVideoRuntime | VideoRuntimeResult: ...

    def prepare_poll(
        self,
        node_run_id: UUID,
        request_id: str,
    ) -> PreparedVideoRuntime | VideoRuntimeResult: ...

    def record_pending(
        self,
        prepared: PreparedVideoRuntime,
        gateway_result: VideoGatewayResult,
    ) -> VideoRuntimeResult: ...

    def complete(
        self,
        prepared: PreparedVideoRuntime,
        gateway_result: VideoGatewayResult,
        validated_file: ValidatedVideoFile,
    ) -> VideoRuntimeResult: ...

    def terminalize_failure(
        self,
        prepared: PreparedVideoRuntime,
        *,
        code: str,
    ) -> None: ...


class VideoRuntimeTransactionFactory(Protocol):
    def begin(self) -> AbstractContextManager[VideoRuntimeTransaction]: ...


class VideoRuntimeGateway(Protocol):
    async def submit_video(
        self,
        request: VideoModelRequest,
        *,
        audit_context: ModelAuditContext,
        media_organization_id: UUID,
    ) -> VideoGatewayResult: ...

    async def poll_video(
        self,
        request: VideoPollRequest,
        *,
        audit_context: ModelAuditContext,
    ) -> VideoGatewayResult: ...


class VideoFileValidator(Protocol):
    def validate(self, file: GeneratedFileFact) -> ValidatedVideoFile: ...
