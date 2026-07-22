"""ORM-free contracts for deterministic artifact quality validation."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID

QualityConclusion = Literal["passed", "failed"]
QualitySourceType = Literal["artifact", "asset"]


def _empty_supporting_inputs() -> Mapping[str, Mapping[str, Any]]:
    return {}


def _empty_supporting_versions() -> Mapping[str, UUID]:
    return {}


def _empty_source_schema() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class ValidatorRef:
    key: str
    semantic_version: str
    implementation_digest: str


@dataclass(frozen=True, slots=True)
class QualityValidationContext:
    organization_id: UUID
    project_id: UUID
    lesson_unit_id: UUID | None
    content_release_id: UUID
    workflow_definition_version_id: UUID
    node_run_id: UUID
    source_type: QualitySourceType
    source_id: UUID
    source_version_id: UUID
    source_content_hash: str
    source_content: Mapping[str, Any]
    validator_refs: tuple[ValidatorRef, ...]
    validator_set_hash: str
    source_schema: Mapping[str, Any] = field(default_factory=_empty_source_schema)
    lesson_key: str | None = None
    supporting_inputs: Mapping[str, Mapping[str, Any]] = field(
        default_factory=_empty_supporting_inputs
    )
    supporting_input_versions: Mapping[str, UUID] = field(
        default_factory=_empty_supporting_versions
    )
    existing_result: ArtifactQualityReportResult | None = None


@dataclass(frozen=True, slots=True)
class ValidatorOutcome:
    validator: ValidatorRef
    passed: bool
    findings: tuple[Mapping[str, Any], ...]
    evidence: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ArtifactQualityReportResult:
    report_id: UUID
    node_run_id: UUID
    conclusion: QualityConclusion


class QualityValidator(Protocol):
    def validate(self, context: QualityValidationContext) -> ValidatorOutcome: ...


class QualityValidatorRegistry(Protocol):
    def resolve(self, refs: tuple[ValidatorRef, ...]) -> tuple[QualityValidator, ...]: ...


class ArtifactQualityTransaction(Protocol):
    def prepare(self, node_run_id: UUID) -> QualityValidationContext: ...

    def complete(
        self,
        context: QualityValidationContext,
        *,
        conclusion: QualityConclusion,
        outcomes: tuple[ValidatorOutcome, ...],
    ) -> ArtifactQualityReportResult: ...

    def fail_technical(self, context: QualityValidationContext, *, code: str) -> None: ...

    def fail_prepare(self, node_run_id: UUID, *, code: str) -> None: ...


@dataclass(frozen=True, slots=True)
class QualitySource:
    source_type: QualitySourceType
    source_id: UUID
    source_version_id: UUID
    content_hash: str
    content: Mapping[str, Any]
    schema: Mapping[str, Any] | None = None


class ArtifactQualityTransactionFactory(Protocol):
    def begin(self) -> AbstractContextManager[ArtifactQualityTransaction]: ...
