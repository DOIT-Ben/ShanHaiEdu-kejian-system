"""Process-local composition registry for reviewed quality validators."""

from __future__ import annotations

from apps.api.artifact_quality.contracts import QualityValidator, ValidatorRef
from apps.api.artifact_quality.registry import InMemoryQualityValidatorRegistry

_VALIDATORS: dict[ValidatorRef, QualityValidator] = {}


def register_runtime_quality_validator(ref: ValidatorRef, validator: QualityValidator) -> None:
    if ref in _VALIDATORS:
        raise ValueError(f"quality validator is already registered: {ref.key}")
    _VALIDATORS[ref] = validator


def runtime_quality_validator_registry() -> InMemoryQualityValidatorRegistry:
    return InMemoryQualityValidatorRegistry(_VALIDATORS)
