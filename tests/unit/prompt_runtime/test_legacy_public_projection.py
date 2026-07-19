from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from apps.api.prompt_runtime.service import _project_legacy_editable_prompt


def canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def content_hash(items: list[dict[str, object]]) -> str:
    return hashlib.sha256(canonical({"items": items}).encode()).hexdigest()


def item(identifier: str, content: object) -> dict[str, object]:
    return {
        "source_id": identifier,
        "source_version_id": f"{identifier}-v1",
        "content": content,
    }


def binding(
    key: str,
    source: str,
    exposure: str,
    items: list[dict[str, object]],
) -> dict[str, object]:
    return {"binding_key": key, "source": source, "exposure": exposure, "items": items}


def summary(value: dict[str, object]) -> dict[str, object]:
    items = value["items"]
    assert isinstance(items, list)
    return {
        "binding_key": value["binding_key"],
        "source": value["source"],
        "exposure": value["exposure"],
        "item_count": len(items),
        "content_hash": content_hash(items),
    }


def technical_chunk(
    summary_value: dict[str, object],
    binding_value: dict[str, object],
) -> str | None:
    exposure = summary_value["exposure"]
    if exposure == "hidden":
        return None
    if exposure == "summary":
        return (
            f"[context:{summary_value['binding_key']}] source={summary_value['source']} "
            f"items={summary_value['item_count']} hash={summary_value['content_hash']}"
        )
    return canonical({"context": binding_value["items"]})


def legacy_case() -> tuple[str, dict[str, object], dict[str, object], str]:
    bindings = [
        binding(
            "preferences",
            "project.teacher_preferences",
            "summary",
            [item("preference-private", {"tone": "warm"})],
        ),
        binding(
            "hidden-rubric",
            "lesson_plan.approved_version",
            "hidden",
            [item("hidden-private", {"rubric": "private"})],
        ),
        binding(
            "material",
            "material.approved_parse",
            "full",
            [
                item("material-a", {"text": "Visible A"}),
                item("material-b", {"text": "Visible B"}),
            ],
        ),
        binding(
            "lesson",
            "lesson_division.approved_version",
            "summary",
            [item("lesson-private", {"lesson": 1})],
        ),
    ]
    summaries = [summary(value) for value in bindings]
    suffix = [
        chunk
        for summary_value, binding_value in zip(summaries, bindings, strict=True)
        if (chunk := technical_chunk(summary_value, binding_value)) is not None
    ]
    business_prompt = "Teacher business text about source and hash vocabulary."
    editable_prompt = "\n\n".join([business_prompt, *suffix])
    preview_json = {"editable_prompt": editable_prompt, "context_summary": summaries}
    bindings_json = {"bindings": bindings}
    expected = "\n\n".join(
        [business_prompt, canonical({"context": [{"text": "Visible A"}, {"text": "Visible B"}]})]
    )
    return editable_prompt, preview_json, bindings_json, expected


def test_valid_legacy_suffix_projects_full_content_without_private_metadata() -> None:
    editable_prompt, preview_json, bindings_json, expected = legacy_case()

    projected = _project_legacy_editable_prompt(editable_prompt, preview_json, bindings_json)

    assert projected == expected
    assert "preference-private" not in projected
    assert "hidden-private" not in projected
    assert "material-a" not in projected
    assert "material-b-v1" not in projected
    assert "lesson-private" not in projected


def test_similar_teacher_json_before_real_suffix_is_preserved() -> None:
    editable_prompt, preview_json, bindings_json, expected = legacy_case()
    teacher_json = canonical(
        {
            "context": [
                {
                    "source_id": "teacher-example",
                    "source_version_id": "teacher-example-v1",
                    "content": {"text": "Keep this teacher example"},
                }
            ]
        }
    )
    editable_prompt = editable_prompt.replace("\n\n", f"\n\n{teacher_json}\n\n", 1)
    preview_json["editable_prompt"] = editable_prompt

    projected = _project_legacy_editable_prompt(editable_prompt, preview_json, bindings_json)

    assert projected == expected.replace("\n\n", f"\n\n{teacher_json}\n\n", 1)
    assert "teacher-example-v1" in projected
    assert "material-a-v1" not in projected


@pytest.mark.parametrize("missing_key", ["source_id", "source_version_id"])
def test_incomplete_legacy_item_is_preserved(missing_key: str) -> None:
    editable_prompt, preview_json, bindings_json, _expected = legacy_case()
    malformed_bindings = deepcopy(bindings_json)
    bindings = malformed_bindings["bindings"]
    assert isinstance(bindings, list)
    material = bindings[2]
    assert isinstance(material, dict)
    items = material["items"]
    assert isinstance(items, list) and isinstance(items[0], dict)
    del items[0][missing_key]

    assert (
        _project_legacy_editable_prompt(editable_prompt, preview_json, malformed_bindings)
        == editable_prompt
    )


def test_legacy_item_with_extra_key_is_preserved() -> None:
    editable_prompt, preview_json, bindings_json, _expected = legacy_case()
    malformed_bindings = deepcopy(bindings_json)
    bindings = malformed_bindings["bindings"]
    assert isinstance(bindings, list)
    material = bindings[2]
    assert isinstance(material, dict)
    items = material["items"]
    assert isinstance(items, list) and isinstance(items[0], dict)
    items[0]["extra"] = "not-old-format"

    assert (
        _project_legacy_editable_prompt(editable_prompt, preview_json, malformed_bindings)
        == editable_prompt
    )


@pytest.mark.parametrize("mutation", ["item_count", "content_hash", "exposure", "order"])
def test_mismatched_legacy_metadata_is_preserved(mutation: str) -> None:
    editable_prompt, preview_json, bindings_json, _expected = legacy_case()
    malformed_preview = deepcopy(preview_json)
    summaries = malformed_preview["context_summary"]
    assert isinstance(summaries, list)
    if mutation == "item_count":
        assert isinstance(summaries[2], dict)
        summaries[2]["item_count"] = 1
    elif mutation == "content_hash":
        assert isinstance(summaries[2], dict)
        summaries[2]["content_hash"] = "0" * 64
    elif mutation == "exposure":
        assert isinstance(summaries[2], dict)
        summaries[2]["exposure"] = "summary"
    else:
        summaries[0], summaries[2] = summaries[2], summaries[0]

    assert (
        _project_legacy_editable_prompt(editable_prompt, malformed_preview, bindings_json)
        == editable_prompt
    )


def test_technical_chunks_must_be_the_complete_ordered_suffix() -> None:
    editable_prompt, preview_json, bindings_json, _expected = legacy_case()
    malformed_prompt = f"{editable_prompt}\n\nTeacher text after technical blocks."
    preview_json["editable_prompt"] = malformed_prompt

    assert (
        _project_legacy_editable_prompt(malformed_prompt, preview_json, bindings_json)
        == malformed_prompt
    )

    chunks = editable_prompt.split("\n\n")
    wrong_order_prompt = "\n\n".join([*chunks[:-3], chunks[-1], chunks[-2], chunks[-3]])
    preview_json["editable_prompt"] = wrong_order_prompt
    assert (
        _project_legacy_editable_prompt(wrong_order_prompt, preview_json, bindings_json)
        == wrong_order_prompt
    )


def test_prompt_without_verified_legacy_metadata_is_unchanged() -> None:
    teacher_prompt = (
        'Teacher JSON: {"context":[{"source_id":"example","content":"keep me"}]} '
        "and ordinary source/hash words."
    )

    assert _project_legacy_editable_prompt(teacher_prompt, {}, {}) == teacher_prompt
