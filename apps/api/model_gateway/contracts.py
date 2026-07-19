"""Platform-owned, provider-neutral model gateway contracts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from workflow.model_capabilities import ModelCapability


@dataclass(frozen=True, slots=True)
class ModelAuditContext:
    organization_id: UUID
    user_id: UUID | None
    project_id: UUID
    node_run_id: UUID
    generation_job_id: UUID | None


class GatewayErrorCode(StrEnum):
    ROUTE_UNAVAILABLE = "MODEL_ROUTE_UNAVAILABLE"
    PROVIDER_UNAVAILABLE = "MODEL_PROVIDER_UNAVAILABLE"
    PROVIDER_AUTH_FAILED = "MODEL_PROVIDER_AUTH_FAILED"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_BUDGET_EXHAUSTED = "MODEL_PROVIDER_BUDGET_EXHAUSTED"
    TIMEOUT = "MODEL_TIMEOUT"
    REJECTED = "GENERATION_REJECTED"
    CANCELLED = "MODEL_CANCELLED"
    INVALID_RESPONSE = "MODEL_INVALID_RESPONSE"
    SUBMISSION_UNKNOWN = "MODEL_SUBMISSION_UNKNOWN"
    AUDIT_UNAVAILABLE = "MODEL_AUDIT_UNAVAILABLE"


class ModelGatewayError(Exception):
    def __init__(
        self,
        code: GatewayErrorCode,
        *,
        retryable: bool,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")


class TextModelRequest(_StrictModel):
    kind: Literal["text"] = "text"
    capability: ModelCapability
    request_id: str = Field(min_length=1, max_length=160)
    prompt: str = Field(min_length=1, max_length=100_000)
    max_output_tokens: int = Field(default=32, ge=1, le=128_000)
    temperature: float = Field(default=0, ge=0, le=2)

    @model_validator(mode="after")
    def require_text_capability(self) -> Self:
        if not self.capability.value.startswith("text."):
            raise ValueError("text requests require a text capability")
        return self


class MediaReference(_StrictModel):
    kind: Literal["file_asset_version"] = "file_asset_version"
    file_version_id: UUID
    mime_type: str = Field(pattern=r"^[a-z0-9.+-]+/[a-z0-9.+-]+$")


class ImageModelRequest(_StrictModel):
    kind: Literal["image"] = "image"
    capability: ModelCapability
    request_id: str = Field(min_length=1, max_length=160)
    prompt: str = Field(min_length=1, max_length=100_000)
    width: int = Field(ge=64, le=8192)
    height: int = Field(ge=64, le=8192)
    references: list[MediaReference] = Field(
        default_factory=lambda: list[MediaReference](),
        max_length=16,
    )

    @model_validator(mode="after")
    def require_image_capability(self) -> Self:
        if not self.capability.value.startswith("image."):
            raise ValueError("image requests require an image capability")
        return self


class VideoModelRequest(_StrictModel):
    kind: Literal["video"] = "video"
    capability: ModelCapability
    request_id: str = Field(min_length=1, max_length=160)
    prompt: str = Field(min_length=1, max_length=100_000)
    duration_seconds: int = Field(ge=1, le=300)
    references: list[MediaReference] = Field(
        default_factory=lambda: list[MediaReference](),
        max_length=16,
    )

    @model_validator(mode="after")
    def require_video_capability(self) -> Self:
        if not self.capability.value.startswith("video."):
            raise ValueError("video requests require a video capability")
        return self


class VideoPollRequest(_StrictModel):
    kind: Literal["video_poll"] = "video_poll"
    capability: ModelCapability
    request_id: str = Field(min_length=1, max_length=160)
    provider_task_id: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def require_video_capability(self) -> Self:
        if not self.capability.value.startswith("video."):
            raise ValueError("video polling requires a video capability")
        return self


ModelRequest = Annotated[
    TextModelRequest | ImageModelRequest | VideoModelRequest,
    Field(discriminator="kind"),
]


UsageUnitName = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")]
UsageUnitValue = Annotated[int, Field(ge=0)]


class ModelUsage(_StrictModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    input_units: dict[UsageUnitName, UsageUnitValue] = Field(default_factory=dict)
    output_units: dict[UsageUnitName, UsageUnitValue] = Field(default_factory=dict)
    cost: Decimal | None = Field(default=None, ge=0, le=Decimal("999999999999.999999"))
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class GeneratedFileFact(_StrictModel):
    kind: Literal["generated_file"] = "generated_file"
    storage_key: str = Field(min_length=1, max_length=1024)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    mime_type: str = Field(pattern=r"^[a-z0-9.+-]+/[a-z0-9.+-]+$")
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    duration_seconds: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_safe_storage_key(self) -> Self:
        segments = self.storage_key.split("/")
        if (
            self.storage_key.startswith("/")
            or "://" in self.storage_key
            or "\\" in self.storage_key
            or any(segment in {"", ".", ".."} for segment in segments)
        ):
            raise ValueError("storage_key must be a safe relative object key")
        return self


class TextProviderResult(_StrictModel):
    kind: Literal["text"] = "text"
    text: str = Field(min_length=1)
    provider_request_id: str | None = Field(default=None, max_length=255)
    actual_model: str = Field(min_length=1, max_length=160)
    finish_reason: str | None = Field(default=None, max_length=80)
    usage: ModelUsage


class ImageProviderResult(_StrictModel):
    kind: Literal["image"] = "image"
    provider_request_id: str | None = Field(default=None, max_length=255)
    actual_model: str = Field(min_length=1, max_length=160)
    files: list[GeneratedFileFact] = Field(min_length=1, max_length=16)
    usage: ModelUsage

    @model_validator(mode="after")
    def require_image_files(self) -> Self:
        _require_media_type(self.files, "image/")
        return self


class VideoOperationStatus(StrEnum):
    SUBMITTED = "submitted"
    POLLING = "polling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUBMISSION_UNKNOWN = "submission_unknown"


class VideoProviderResult(_StrictModel):
    kind: Literal["video"] = "video"
    status: VideoOperationStatus
    provider_request_id: str | None = Field(default=None, max_length=255)
    provider_task_id: str | None = Field(default=None, max_length=255)
    actual_model: str = Field(min_length=1, max_length=160)
    files: list[GeneratedFileFact] = Field(
        default_factory=lambda: list[GeneratedFileFact](),
        max_length=16,
    )
    usage: ModelUsage

    @model_validator(mode="after")
    def require_state_facts(self) -> Self:
        _require_video_state(self.status, self.provider_task_id, self.files)
        return self


class RouteDecision(_StrictModel):
    capability: ModelCapability
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=80)


class TextGatewayResult(_StrictModel):
    kind: Literal["text"] = "text"
    request_id: str
    text: str
    route: RouteDecision
    provider_request_id: str | None
    actual_model: str
    finish_reason: str | None
    usage: ModelUsage
    latency_ms: int = Field(ge=0)


class ImageGatewayResult(_StrictModel):
    kind: Literal["image"] = "image"
    request_id: str
    route: RouteDecision
    provider_request_id: str | None
    actual_model: str
    files: list[GeneratedFileFact] = Field(min_length=1, max_length=16)
    usage: ModelUsage
    latency_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def require_image_files(self) -> Self:
        _require_media_type(self.files, "image/")
        return self


class VideoGatewayResult(_StrictModel):
    kind: Literal["video"] = "video"
    request_id: str
    status: VideoOperationStatus
    route: RouteDecision
    provider_request_id: str | None
    provider_task_id: str | None
    actual_model: str
    files: list[GeneratedFileFact] = Field(
        default_factory=lambda: list[GeneratedFileFact](),
        max_length=16,
    )
    usage: ModelUsage
    latency_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def require_state_facts(self) -> Self:
        _require_video_state(self.status, self.provider_task_id, self.files)
        return self


ModelResult = Annotated[
    TextGatewayResult | ImageGatewayResult | VideoGatewayResult,
    Field(discriminator="kind"),
]


def _require_video_state(
    status: VideoOperationStatus,
    provider_task_id: str | None,
    files: list[GeneratedFileFact],
) -> None:
    recoverable = {
        VideoOperationStatus.SUBMITTED,
        VideoOperationStatus.POLLING,
        VideoOperationStatus.SUCCEEDED,
        VideoOperationStatus.FAILED,
        VideoOperationStatus.CANCELLED,
    }
    if status in recoverable and not provider_task_id:
        raise ValueError("recoverable video states require provider_task_id")
    if status == VideoOperationStatus.SUCCEEDED:
        if not files:
            raise ValueError("succeeded video results require generated file facts")
        _require_media_type(files, "video/")
    elif files:
        raise ValueError("only succeeded video results may contain files")


def _require_media_type(files: list[GeneratedFileFact], expected_prefix: str) -> None:
    if any(not file.mime_type.startswith(expected_prefix) for file in files):
        raise ValueError(f"generated files must use {expected_prefix} MIME types")
