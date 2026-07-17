"""Platform-owned model gateway contracts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelCapability(StrEnum):
    TEXT_SMOKE = "text.smoke"


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


class TextModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: ModelCapability
    request_id: str = Field(min_length=1, max_length=160)
    prompt: str = Field(min_length=1, max_length=4_000)
    max_output_tokens: int = Field(default=32, ge=1, le=256)
    temperature: float = Field(default=0, ge=0, le=2)


class ModelUsage(BaseModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class TextProviderResult(BaseModel):
    text: str = Field(min_length=1)
    provider_request_id: str | None = None
    actual_model: str
    finish_reason: str | None = None
    usage: ModelUsage


class RouteDecision(BaseModel):
    capability: ModelCapability
    provider: str
    model: str
    reason: str


class TextGatewayResult(BaseModel):
    request_id: str
    text: str
    route: RouteDecision
    provider_request_id: str | None
    actual_model: str
    finish_reason: str | None
    usage: ModelUsage
    latency_ms: int = Field(ge=0)
