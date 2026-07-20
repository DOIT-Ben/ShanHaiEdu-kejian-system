"""Strict extraction and schema validation for generated JSON objects."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, NoReturn, Protocol, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


class _SchemaValidator(Protocol):
    def iter_errors(self, instance: object) -> Iterable[ValidationError]: ...


@dataclass(frozen=True, slots=True)
class StructuredOutputError(ValueError):
    code: str
    message: str
    details: tuple[dict[str, object], ...] = ()

    def __str__(self) -> str:
        return self.message


def validate_structured_output(
    text: str,
    schema: dict[str, object],
) -> dict[str, Any]:
    """Apply one syntax-only repair, then enforce the published output schema."""

    validator = _build_validator(schema)
    payload = _decode_json_object(_strip_json_fence(text))
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: (tuple(str(part) for part in error.absolute_path), error.validator or ""),
    )
    if errors:
        raise StructuredOutputError(
            "MODEL_OUTPUT_SCHEMA_INVALID",
            "model output does not match the published schema",
            tuple(
                {
                    "path": list(error.absolute_path),
                    "validator": error.validator or "unknown",
                }
                for error in errors
            ),
        )
    return payload


def _build_validator(schema: dict[str, object]) -> _SchemaValidator:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise StructuredOutputError(
            "MODEL_OUTPUT_SCHEMA_UNSUPPORTED",
            "published output schema is invalid",
        ) from exc
    return cast(_SchemaValidator, Draft202012Validator(schema))


def _strip_json_fence(text: str) -> str:
    if text.startswith("```json\n") and text.endswith("\n```"):
        return text[8:-4]
    return text


def _decode_json_object(text: str) -> dict[str, Any]:
    try:
        value = cast(object, json.loads(text, parse_constant=_reject_nonfinite_constant))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StructuredOutputError(
            "MODEL_OUTPUT_JSON_INVALID",
            "model output is not one JSON document",
        ) from exc
    if type(value) is not dict:
        raise StructuredOutputError(
            "MODEL_OUTPUT_OBJECT_REQUIRED",
            "model output must be a JSON object",
        )
    return cast(dict[str, Any], value)


def _reject_nonfinite_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")
