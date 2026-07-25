from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import pytest

from tests.integration.r1_text_provider_stub import _provider_request_id, build_structured_output


def test_allocates_a_unique_provider_request_id_per_call() -> None:
    first = _provider_request_id()
    second = _provider_request_id()

    assert first != second
    UUID(first.removeprefix("r1-deterministic-http-"))
    UUID(second.removeprefix("r1-deterministic-http-"))


def test_builds_exact_r1_outputs_from_declared_context() -> None:
    evidence_keys = ["page-1:block-1", "page-2:block-1"]
    division = build_structured_output(
        _prompt(
            _context("material_scope.approved_version", {"approved_evidence_keys": evidence_keys}),
            _schema("division_key"),
        )
    )

    assert division["lesson_count"] == 2
    assert [
        evidence for unit in division["lesson_units"] for evidence in unit["evidence_refs"]
    ] == evidence_keys

    lesson_unit = division["lesson_units"][0]
    lesson_plan = build_structured_output(
        _prompt(
            _context(
                "lesson_division.approved_version",
                {"division_key": division["division_key"], "lesson_unit": lesson_unit},
            ),
            _schema("teaching_content"),
        )
    )

    assert lesson_plan["teaching_content"]["source_lesson_unit_key"] == "LESSON-001"
    assert lesson_plan["teaching_content"]["teaching_evidence_refs"] == ["page-1:block-1"]

    intro = build_structured_output(
        _prompt(
            _context(
                "lesson_division.approved_version",
                {"division_key": division["division_key"], "lesson_unit": lesson_unit},
            ),
            _schema("option_set_key"),
        )
    )

    assert len(intro["options"]) == 9
    assert intro["source_lesson_unit_key"] == "LESSON-001"
    assert intro["source_material_evidence_keys"] == ["page-1:block-1"]


def test_rejects_output_that_does_not_match_request_schema() -> None:
    schema = _schema("division_key")
    schema["properties"] = {"division_key": {"const": "not-the-r1-division"}}

    with pytest.raises(ValueError, match="request schema"):
        build_structured_output(
            _prompt(
                _context(
                    "material_scope.approved_version",
                    {"approved_evidence_keys": ["page-1:block-1", "page-2:block-1"]},
                ),
                schema,
            )
        )


def _context(source: str, content: dict[str, Any]) -> dict[str, Any]:
    return {
        "bindings": [
            {
                "binding_key": source,
                "exposure": "full",
                "items": [
                    {
                        "content": content,
                        "source_id": "source-1",
                        "source_version_id": "version-1",
                    }
                ],
                "source": source,
            }
        ]
    }


def _schema(required: str) -> dict[str, Any]:
    return {
        "additionalProperties": True,
        "properties": {required: {}},
        "required": [required],
        "type": "object",
    }


def _prompt(context: dict[str, Any], schema: dict[str, Any]) -> str:
    return (
        "[context:declared_context]\n"
        f"{json.dumps(context, sort_keys=True)}\n\n"
        "[output_schema:request_schema]\n"
        f"{json.dumps(schema, sort_keys=True)}\n\n"
        "[provider_format:provider_format]\n"
        "Return exactly one JSON object and no commentary."
    )
