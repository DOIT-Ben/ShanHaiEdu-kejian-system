"""Published context-source registry and storage resolver declarations."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

ContextSourceResolverKind = Literal["artifact", "asset", "project"]
ContextSourceScope = Literal["project", "lesson"]


@dataclass(frozen=True, slots=True)
class ContextSourceDefinition:
    resolver_kind: ContextSourceResolverKind
    contract_ref: str
    artifact_types: tuple[str, ...] = ()
    scope: ContextSourceScope | None = None
    branch_key: str | None = None
    requires_current_approval: bool = False


CONTEXT_SOURCE_REGISTRY = MappingProxyType(
    {
        "asset_slot.current_version": ContextSourceDefinition("asset", "asset_slot:current"),
        "intro_selection.snapshot": ContextSourceDefinition(
            "artifact", "selection:intro", ("intro_selection",), "lesson", "intro_options"
        ),
        "lesson_division.approved_version": ContextSourceDefinition(
            "artifact",
            "approval:lesson_division",
            ("lesson_division",),
            "project",
            "project",
            True,
        ),
        "lesson_plan.approved_version": ContextSourceDefinition(
            "artifact",
            "approval:lesson_plan",
            ("lesson_plan",),
            "lesson",
            "lesson_plan",
            True,
        ),
        "material.approved_parse": ContextSourceDefinition("asset", "content:material_evidence"),
        "material_scope.approved_version": ContextSourceDefinition(
            "artifact",
            "approval:material_scope",
            ("material_scope",),
            "project",
            "project",
            True,
        ),
        "ppt_outline.approved_version": ContextSourceDefinition(
            "artifact", "approval:ppt_outline", ("ppt_outline",), "lesson", "ppt", True
        ),
        "ppt_page_spec.current_version": ContextSourceDefinition(
            "artifact",
            "artifact:ppt_page_specs",
            ("ppt_page_specs", "ppt_page_spec_set"),
            "lesson",
            "ppt",
        ),
        "ppt_style.approved_version": ContextSourceDefinition(
            "artifact", "contract:ppt_style", ("ppt_style",), "lesson", "ppt", True
        ),
        "project.teacher_preferences": ContextSourceDefinition(
            "project", "project:teacher_preferences"
        ),
        "video.asset_inventory.current_version": ContextSourceDefinition(
            "artifact",
            "artifact:video_asset_inventory",
            ("video_asset_inventory",),
            "lesson",
            "video",
        ),
        "video.assets.approved_versions": ContextSourceDefinition(
            "artifact",
            "artifact:video_asset_generation_batch",
            ("video_asset_generation_batch",),
            "lesson",
            "video",
        ),
        "video.clips.approved_versions": ContextSourceDefinition(
            "asset", "asset:video_selected_clips"
        ),
        "video.master_script.approved_version": ContextSourceDefinition(
            "artifact",
            "approval:video_master_script",
            ("video_master_script",),
            "lesson",
            "video",
            True,
        ),
        "video.rough_storyboard.approved_version": ContextSourceDefinition(
            "artifact",
            "approval:video_rough_storyboard",
            ("video_rough_storyboard",),
            "lesson",
            "video",
            True,
        ),
        "video.style.approved_version": ContextSourceDefinition(
            "artifact",
            "contract:video_style",
            ("video_style_master_image_candidates",),
            "lesson",
            "video",
            True,
        ),
    }
)


# Input contract references are a separate published namespace from context keys.
ARTIFACT_CONTRACT_REGISTRY = MappingProxyType(
    {
        "approval:material_scope": ContextSourceDefinition(
            "artifact",
            "approval:material_scope",
            ("material_scope",),
            "project",
            "project",
            True,
        ),
        "artifact:material_scope": ContextSourceDefinition(
            "artifact", "artifact:material_scope", ("material_scope",), "project", "project"
        ),
        "approval:lesson_division": CONTEXT_SOURCE_REGISTRY["lesson_division.approved_version"],
        "artifact:lesson_division": ContextSourceDefinition(
            "artifact", "artifact:lesson_division", ("lesson_division",), "project", "project"
        ),
        "approval:lesson_plan": CONTEXT_SOURCE_REGISTRY["lesson_plan.approved_version"],
        "artifact:lesson_plan": ContextSourceDefinition(
            "artifact", "artifact:lesson_plan", ("lesson_plan",), "lesson", "lesson_plan"
        ),
        "artifact:intro_option_set": ContextSourceDefinition(
            "artifact",
            "artifact:intro_option_set",
            ("intro_option_set",),
            "lesson",
            "intro_options",
        ),
        "artifact:ppt_outline": ContextSourceDefinition(
            "artifact", "artifact:ppt_outline", ("ppt_outline",), "lesson", "ppt"
        ),
        "artifact:ppt_page_specs": CONTEXT_SOURCE_REGISTRY["ppt_page_spec.current_version"],
        "approval:ppt_outline": CONTEXT_SOURCE_REGISTRY["ppt_outline.approved_version"],
        "contract:ppt_style": CONTEXT_SOURCE_REGISTRY["ppt_style.approved_version"],
        "approval:ppt_cover": ContextSourceDefinition(
            "artifact",
            "approval:ppt_cover",
            ("ppt_cover_image_candidates",),
            "lesson",
            "ppt",
            True,
        ),
        "approval:ppt_final": ContextSourceDefinition(
            "artifact", "approval:ppt_final", ("ppt_final",), "lesson", "ppt", True
        ),
        "artifact:ppt_page_previews": ContextSourceDefinition(
            "artifact", "artifact:ppt_page_previews", ("ppt_page_previews",), "lesson", "ppt"
        ),
        "artifact:video_asset_inventory": CONTEXT_SOURCE_REGISTRY[
            "video.asset_inventory.current_version"
        ],
        "artifact:video_master_script": ContextSourceDefinition(
            "artifact",
            "artifact:video_master_script",
            ("video_master_script",),
            "lesson",
            "video",
        ),
        "approval:video_master_script": CONTEXT_SOURCE_REGISTRY[
            "video.master_script.approved_version"
        ],
        "artifact:video_rough_storyboard": ContextSourceDefinition(
            "artifact",
            "artifact:video_rough_storyboard",
            ("video_rough_storyboard",),
            "lesson",
            "video",
        ),
        "approval:video_rough_storyboard": CONTEXT_SOURCE_REGISTRY[
            "video.rough_storyboard.approved_version"
        ],
        "artifact:video_fine_storyboard": ContextSourceDefinition(
            "artifact",
            "artifact:video_fine_storyboard",
            ("video_fine_storyboard",),
            "lesson",
            "video",
        ),
        "artifact:audio_plan": ContextSourceDefinition(
            "artifact", "artifact:audio_plan", ("audio_plan",), "lesson", "video"
        ),
        "approval:video_final": ContextSourceDefinition(
            "artifact", "approval:video_final", ("video_final",), "lesson", "video", True
        ),
        "artifact:subtitles": ContextSourceDefinition(
            "artifact", "artifact:subtitles", ("subtitles",), "lesson", "video"
        ),
        "contract:video_style": CONTEXT_SOURCE_REGISTRY["video.style.approved_version"],
        "selection:intro": CONTEXT_SOURCE_REGISTRY["intro_selection.snapshot"],
    }
)


DEFAULT_CONTEXT_SOURCES = frozenset(CONTEXT_SOURCE_REGISTRY)
