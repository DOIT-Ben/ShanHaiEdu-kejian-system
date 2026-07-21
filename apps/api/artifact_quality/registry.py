"""Exact callable registry for versioned quality validators."""

from __future__ import annotations

from collections.abc import Mapping

from apps.api.artifact_quality.contracts import QualityValidator, ValidatorRef


class QualityValidatorRegistryError(LookupError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class InMemoryQualityValidatorRegistry:
    def __init__(self, validators: Mapping[ValidatorRef, QualityValidator]) -> None:
        self._validators = dict(validators)

    def resolve(self, refs: tuple[ValidatorRef, ...]) -> tuple[QualityValidator, ...]:
        resolved: list[QualityValidator] = []
        for ref in refs:
            validator = self._validators.get(ref)
            if validator is None:
                raise QualityValidatorRegistryError(
                    "QUALITY_VALIDATOR_UNAVAILABLE",
                    f"quality validator is unavailable: {ref.key}@{ref.semantic_version}",
                )
            resolved.append(validator)
        return tuple(resolved)
