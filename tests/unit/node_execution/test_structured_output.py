from __future__ import annotations

import pytest

from apps.api.node_execution.structured_output import (
    StructuredOutputError,
    validate_structured_output,
)

OUTPUT_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "sections"],
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "sections": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
    },
}


def test_accepts_a_valid_json_object_without_rewriting_values() -> None:
    result = validate_structured_output(
        '{"title":"Lesson 1","sections":["Explore","Practice"]}',
        OUTPUT_SCHEMA,
    )

    assert result == {"title": "Lesson 1", "sections": ["Explore", "Practice"]}


def test_applies_one_strict_json_fence_repair() -> None:
    result = validate_structured_output(
        '```json\n{"title":"Lesson 1","sections":["Explore"]}\n```',
        OUTPUT_SCHEMA,
    )

    assert result == {"title": "Lesson 1", "sections": ["Explore"]}


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ('prefix {"title":"Lesson 1","sections":["Explore"]}', "MODEL_OUTPUT_JSON_INVALID"),
        ('["not", "an", "object"]', "MODEL_OUTPUT_OBJECT_REQUIRED"),
        (
            '```python\n{"title":"Lesson 1","sections":["Explore"]}\n```',
            "MODEL_OUTPUT_JSON_INVALID",
        ),
    ],
)
def test_rejects_unbounded_or_ambiguous_repairs(text: str, code: str) -> None:
    with pytest.raises(StructuredOutputError) as caught:
        validate_structured_output(text, OUTPUT_SCHEMA)

    assert caught.value.code == code


def test_rejects_content_that_does_not_match_the_published_schema() -> None:
    with pytest.raises(StructuredOutputError) as caught:
        validate_structured_output(
            '{"title":"Lesson 1","sections":["Explore"],"video":true}',
            OUTPUT_SCHEMA,
        )

    assert caught.value.code == "MODEL_OUTPUT_SCHEMA_INVALID"
    assert caught.value.details == ({"path": [], "validator": "additionalProperties"},)


def test_rejects_an_invalid_published_schema_before_content_validation() -> None:
    with pytest.raises(StructuredOutputError) as caught:
        validate_structured_output("{}", {"type": "unknown"})

    assert caught.value.code == "MODEL_OUTPUT_SCHEMA_UNSUPPORTED"
