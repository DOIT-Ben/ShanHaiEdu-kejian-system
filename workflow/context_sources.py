"""Published context-source registry and storage resolver declarations."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

ContextSourceResolverKind = Literal["artifact", "asset", "project"]


@dataclass(frozen=True, slots=True)
class ContextSourceDefinition:
    resolver_kind: ContextSourceResolverKind
    contract_ref: str
    artifact_types: tuple[str, ...] = ()


CONTEXT_SOURCE_REGISTRY = MappingProxyType(
    {
        "asset_slot.current_version": ContextSourceDefinition("asset", "asset_slot:current"),
        "intro_selection.snapshot": ContextSourceDefinition(
            "artifact", "selection:intro", ("intro_selection",)
        ),
        "lesson_division.approved_version": ContextSourceDefinition(
            "artifact", "approval:lesson_division", ("lesson_division",)
        ),
        "lesson_plan.approved_version": ContextSourceDefinition(
            "artifact", "approval:lesson_plan", ("lesson_plan",)
        ),
        "material.approved_parse": ContextSourceDefinition("asset", "content:material_evidence"),
        "ppt_outline.approved_version": ContextSourceDefinition(
            "artifact", "approval:ppt_outline", ("ppt_outline",)
        ),
        "ppt_page_spec.current_version": ContextSourceDefinition(
            "artifact", "artifact:ppt_page_specs", ("ppt_page_specs", "ppt_page_spec_set")
        ),
        "ppt_style.approved_version": ContextSourceDefinition(
            "artifact", "contract:ppt_style", ("ppt_style",)
        ),
        "project.teacher_preferences": ContextSourceDefinition(
            "project", "project:teacher_preferences"
        ),
        "video.asset_inventory.current_version": ContextSourceDefinition(
            "artifact", "artifact:video_asset_inventory", ("video_asset_inventory",)
        ),
        "video.assets.approved_versions": ContextSourceDefinition(
            "artifact", "artifact:video_asset_generation_batch", ("video_asset_generation_batch",)
        ),
        "video.clips.approved_versions": ContextSourceDefinition(
            "artifact", "asset:video_selected_clips", ("video_shot_generation",)
        ),
        "video.master_script.approved_version": ContextSourceDefinition(
            "artifact", "approval:video_master_script", ("video_master_script",)
        ),
        "video.rough_storyboard.approved_version": ContextSourceDefinition(
            "artifact", "approval:video_rough_storyboard", ("video_rough_storyboard",)
        ),
        "video.style.approved_version": ContextSourceDefinition(
            "artifact", "contract:video_style", ("video_style_master_image_candidates",)
        ),
    }
)


DEFAULT_CONTEXT_SOURCES = frozenset(CONTEXT_SOURCE_REGISTRY)
