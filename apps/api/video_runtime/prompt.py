"""Compile the release-bound prompt for the one-keyframe video node."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from apps.api.content_runtime.runtime_port import RuntimeNodeMaterials
from apps.api.intro_selections.schemas import IntroSelectionRead
from workflow.prompt_runtime import (
    AssembledContext,
    CompiledPrompt,
    ContextBinding,
    ContextItem,
    PromptSection,
    assemble_context,
    compile_prompt,
)

from .contracts import VideoRuntimeError

_CAPABILITY = "video.image_to_video.6s_30s"
_SOURCE = "intro_selection.snapshot"
_STYLE = "style.primary_math.paper_clay"
_PLATFORM_SAFETY = "Enforce tenant isolation, child safety, and the published video contract."
_PROVIDER_FORMAT = "Return one provider-managed MP4 candidate and no explanatory text."


@dataclass(frozen=True, slots=True)
class CompiledVideoPrompt:
    context: AssembledContext
    prompt: CompiledPrompt


def compile_video_prompt(
    materials: RuntimeNodeMaterials,
    selection: IntroSelectionRead,
) -> CompiledVideoPrompt:
    definition = materials.definition
    generation = _mapping(definition.generation_template.get("spec"))
    prompt_spec = _mapping(materials.prompt_template.get("spec"))
    policy = _mapping(definition.node_binding.get("context_policy"))
    allowed_sources = frozenset(_strings(policy.get("allowed_sources")))
    style_refs = tuple(
        _mapping(value).get("item_key") for value in _sequence(generation.get("style_preset_refs"))
    )
    if (
        definition.node_key != "video.shots.generate"
        or definition.execution_kind != "model_generation"
        or definition.node_binding.get("model_capability") != _CAPABILITY
        or generation.get("model_capability") != _CAPABILITY
        or prompt_spec.get("model_capability") != _CAPABILITY
        or generation.get("template_key") != "video.shots.generate"
        or prompt_spec.get("template_key") != "video.shots.generate.prompt"
        or allowed_sources != frozenset({_SOURCE})
        or style_refs != (_STYLE,)
    ):
        raise VideoRuntimeError(
            "VIDEO_RUNTIME_RELEASE_INVALID",
            "the published video runtime contract is not the 1.5.0 golden node",
        )
    bindings = tuple(
        _context_binding(value) for value in _sequence(prompt_spec.get("context_bindings"))
    )
    if len(bindings) != 1 or bindings[0].source != _SOURCE:
        raise VideoRuntimeError(
            "VIDEO_RUNTIME_RELEASE_INVALID",
            "the video prompt must consume only the exact Intro selection",
        )
    context = assemble_context(
        bindings,
        {
            _SOURCE: (
                ContextItem(
                    source=_SOURCE,
                    source_id=str(selection.id),
                    source_version_id=str(selection.artifact_version_id),
                    content=selection.snapshot,
                ),
            )
        },
        allowed_sources=allowed_sources,
    )
    edit_policy = _mapping(prompt_spec.get("user_edit_policy"))
    prompt = compile_prompt(
        template_key=cast(str, prompt_spec["template_key"]),
        template_version=str(definition.content_release_id),
        platform_safety=_PLATFORM_SAFETY,
        sections=tuple(_prompt_section(value) for value in _sequence(prompt_spec.get("sections"))),
        context=context,
        output_schema=materials.output_schema,
        provider_format=_PROVIDER_FORMAT,
        user_edit_mode="replace_editable_layer",
        user_edit_max_chars=_integer(edit_policy.get("max_chars")),
    )
    return CompiledVideoPrompt(context=context, prompt=prompt)


def _context_binding(value: object) -> ContextBinding:
    item = _mapping(value)
    return ContextBinding(
        binding_key=_text(item.get("binding_key")),
        source=_text(item.get("source")),
        required=_boolean(item.get("required")),
        exposure=cast(Any, _text(item.get("exposure"))),
        max_items=_integer(item.get("max_items")),
        max_bytes=_integer(item.get("max_bytes")),
    )


def _prompt_section(value: object) -> PromptSection:
    item = _mapping(value)
    return PromptSection(
        section_key=_text(item.get("section_key")),
        layer=_text(item.get("layer")),
        content=_text(item.get("content")),
        editable=_boolean(item.get("editable")),
        visible_to_teacher=_boolean(item.get("visible_to_teacher")),
    )


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VideoRuntimeError("VIDEO_RUNTIME_RELEASE_INVALID", "video release mapping is invalid")
    return cast(Mapping[str, Any], value)


def _sequence(value: object) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise VideoRuntimeError("VIDEO_RUNTIME_RELEASE_INVALID", "video release list is invalid")
    return cast(Sequence[object], value)


def _strings(value: object) -> tuple[str, ...]:
    values = _sequence(value)
    if any(type(item) is not str for item in values):
        raise VideoRuntimeError(
            "VIDEO_RUNTIME_RELEASE_INVALID", "video release strings are invalid"
        )
    return tuple(cast(str, item) for item in values)


def _text(value: object) -> str:
    if type(value) is not str or not value:
        raise VideoRuntimeError("VIDEO_RUNTIME_RELEASE_INVALID", "video release text is invalid")
    return value


def _integer(value: object) -> int:
    if type(value) is not int or value < 1:
        raise VideoRuntimeError("VIDEO_RUNTIME_RELEASE_INVALID", "video release limit is invalid")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise VideoRuntimeError("VIDEO_RUNTIME_RELEASE_INVALID", "video release flag is invalid")
    return value
