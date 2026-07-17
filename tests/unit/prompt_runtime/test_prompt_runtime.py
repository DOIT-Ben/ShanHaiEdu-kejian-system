from __future__ import annotations

import pytest

from workflow.prompt_runtime import (
    ContextBinding,
    ContextExposure,
    ContextItem,
    PromptRuntimeError,
    PromptSection,
    assemble_context,
    compile_prompt,
)


def binding(
    key: str,
    source: str,
    *,
    required: bool = True,
    exposure: ContextExposure = "full",
    max_items: int = 2,
    max_bytes: int = 1_000,
) -> ContextBinding:
    return ContextBinding(
        binding_key=key,
        source=source,
        required=required,
        exposure=exposure,
        max_items=max_items,
        max_bytes=max_bytes,
    )


def item(source: str, identifier: str, content: object) -> ContextItem:
    return ContextItem(
        source=source,
        source_id=identifier,
        source_version_id=f"{identifier}-v1",
        content=content,
    )


def test_context_assembler_rejects_an_undeclared_source_before_provider_use() -> None:
    with pytest.raises(PromptRuntimeError) as caught:
        assemble_context(
            (binding("material", "material.approved_parse"),),
            {
                "material.approved_parse": (
                    item("material.approved_parse", "material-1", {"text": "allowed"}),
                ),
                "lesson_plan.approved_version": (
                    item("lesson_plan.approved_version", "plan-1", {"text": "forbidden"}),
                ),
            },
        )

    assert caught.value.code == "CONTEXT_SOURCE_NOT_DECLARED"


def test_context_assembler_rejects_unregistered_and_missing_required_sources() -> None:
    with pytest.raises(PromptRuntimeError) as unregistered:
        assemble_context((binding("private", "private.internal"),), {})
    assert unregistered.value.code == "CONTEXT_SOURCE_FORBIDDEN"

    with pytest.raises(PromptRuntimeError) as missing:
        assemble_context((binding("material", "material.approved_parse"),), {})
    assert missing.value.code == "CONTEXT_REQUIRED_MISSING"


@pytest.mark.parametrize(
    ("declared", "values", "code"),
    [
        (
            binding("material", "material.approved_parse", max_items=1),
            (
                item("material.approved_parse", "first", {"text": "one"}),
                item("material.approved_parse", "second", {"text": "two"}),
            ),
            "CONTEXT_ITEM_LIMIT_EXCEEDED",
        ),
        (
            binding("material", "material.approved_parse", max_bytes=10),
            (item("material.approved_parse", "large", {"text": "x" * 100}),),
            "CONTEXT_BYTE_LIMIT_EXCEEDED",
        ),
    ],
)
def test_context_assembler_enforces_declared_limits(
    declared: ContextBinding,
    values: tuple[ContextItem, ...],
    code: str,
) -> None:
    with pytest.raises(PromptRuntimeError) as caught:
        assemble_context((declared,), {declared.source: values})

    assert caught.value.code == code


def test_context_snapshot_is_deterministic_and_records_source_versions() -> None:
    declared = (binding("material", "material.approved_parse"),)
    first = assemble_context(
        declared,
        {
            "material.approved_parse": (
                item("material.approved_parse", "b", {"page": 2, "text": "B"}),
                item("material.approved_parse", "a", {"text": "A", "page": 1}),
            )
        },
    )
    second = assemble_context(
        declared,
        {
            "material.approved_parse": (
                item("material.approved_parse", "a", {"page": 1, "text": "A"}),
                item("material.approved_parse", "b", {"text": "B", "page": 2}),
            )
        },
    )

    assert first == second
    assert first.content_hash == second.content_hash
    assert [value["source_id"] for value in first.bindings[0]["items"]] == ["a", "b"]
    assert first.bindings[0]["items"][0]["source_version_id"] == "a-v1"


def test_prompt_compiler_is_deterministic_and_preview_is_privacy_safe() -> None:
    context = assemble_context(
        (
            binding("material", "material.approved_parse", exposure="summary"),
            binding(
                "preferences",
                "project.teacher_preferences",
                exposure="hidden",
            ),
        ),
        {
            "material.approved_parse": (
                item("material.approved_parse", "material-1", {"text": "MATERIAL_PRIVATE"}),
            ),
            "project.teacher_preferences": (
                item(
                    "project.teacher_preferences",
                    "preference-1",
                    {"text": "PREFERENCE_PRIVATE"},
                ),
            ),
        },
    )
    sections = (
        PromptSection("role", "role", "You are a teacher.", False, True),
        PromptSection("method", "method", "Use a visual method.", True, True),
        PromptSection("quality", "quality_gate", "Internal quality gate.", False, False),
    )

    first = compile_prompt(
        template_key="lesson-plan.prompt",
        template_version="1.0.0",
        platform_safety="PLATFORM_PRIVATE",
        sections=sections,
        context=context,
        output_schema={"required": ["answer"], "type": "object"},
        provider_format="PROVIDER_PRIVATE",
    )
    second = compile_prompt(
        template_key="lesson-plan.prompt",
        template_version="1.0.0",
        platform_safety="PLATFORM_PRIVATE",
        sections=sections,
        context=context,
        output_schema={"type": "object", "required": ["answer"]},
        provider_format="PROVIDER_PRIVATE",
    )

    assert first == second
    assert "PLATFORM_PRIVATE" in first.compiled_prompt
    assert "MATERIAL_PRIVATE" in first.compiled_prompt
    assert "PREFERENCE_PRIVATE" in first.compiled_prompt
    assert "PROVIDER_PRIVATE" in first.compiled_prompt
    assert "You are a teacher." in first.preview.editable_prompt
    assert "Use a visual method." in first.preview.editable_prompt
    rendered_preview = repr(first.preview)
    assert "PLATFORM_PRIVATE" not in rendered_preview
    assert "MATERIAL_PRIVATE" not in rendered_preview
    assert "PREFERENCE_PRIVATE" not in rendered_preview
    assert "PROVIDER_PRIVATE" not in rendered_preview
    assert {layer["layer"] for layer in first.preview.locked_layers} == {
        "platform_safety",
        "output_schema",
        "provider_format",
    }


def test_prompt_revision_only_replaces_the_editable_business_layer() -> None:
    compiled = compile_prompt(
        template_key="lesson-plan.prompt",
        template_version="1.0.0",
        platform_safety="locked safety",
        sections=(
            PromptSection("role", "role", "locked role", False, True),
            PromptSection("method", "method", "base editable method", True, True),
        ),
        context=assemble_context((), {}),
        output_schema={"type": "object"},
        provider_format="locked provider format",
        user_revision="teacher replacement",
    )

    assert "teacher replacement" in compiled.editable_prompt
    assert "base editable method" not in compiled.editable_prompt
    assert "locked role" in compiled.editable_prompt
    assert compiled.user_diff == {
        "mode": "replace_editable_layer",
        "replacement": "teacher replacement",
    }
    assert "locked safety" in compiled.compiled_prompt
    assert "locked provider format" in compiled.compiled_prompt
