"""Build reusable inputs between golden planning stages."""

from __future__ import annotations

import copy
from typing import Any, cast

from scripts.golden_courseware_branch_inputs import (
    build_golden_branch_source_outputs,
    build_golden_branch_start_inputs,
)

GOLDEN_CHAIN_INPUT_NODE_KEYS = (
    "intro.generate_options",
    "ppt.outline.generate",
    "ppt.pages.generate",
    "ppt.cover.prompt.generate",
    "ppt.body_asset_prompts.generate",
    "video.rough_storyboard.generate",
    "video.style_master.prompt.generate",
    "video.asset_inventory.generate",
    "video.asset_prompts.generate",
)

MEDIA_BOUNDARY_OUTPUT_ONLY_NODE_KEYS = (
    "video.fine_storyboard.generate",
    "audio.plan.generate",
)


def build_golden_chain_inputs(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Connect planning outputs until a real approved-media input is required."""

    outputs = build_golden_branch_source_outputs(case)
    starts = build_golden_branch_start_inputs(case)
    lesson_plan = outputs["lesson_plan.generate"]
    lesson_unit = starts["lesson_plan.generate"]["lesson_unit_ref"]
    material = starts["lesson_plan.generate"]["material_evidence_ref"]
    selected_intro = starts["video.master_script.generate"]["selected_intro_snapshot_ref"]
    ppt = cast(dict[str, Any], case["ppt"])
    video = cast(dict[str, Any], case["video"])
    preferences = cast(dict[str, Any], case["teacher_preferences"])
    pages = outputs["ppt.pages.generate"]
    cover_page = next(page for page in pages["page_specs"] if page["page_type"] == "cover")

    return {
        "intro.generate_options": {
            "generation_mode": case["intro_option_set"]["generation_mode"],
            "target_lesson_unit": copy.deepcopy(lesson_unit),
            "knowledge_point": lesson_unit["teaching_focus"],
            "learning_objective_summary": lesson_unit["core_learning_outcome"],
            "teaching_content_boundary": lesson_unit["content_boundary"],
            "must_not_preteach": copy.deepcopy(lesson_unit["must_not_preteach"]),
            "grade_level": case["project"]["grade"],
            "audience_age_band": "6-7岁",
            "target_material_evidence": copy.deepcopy(material),
            "duration_preference_seconds": selected_intro["duration_seconds"],
            "general_teacher_preferences": copy.deepcopy(preferences),
        },
        "ppt.outline.generate": {
            "ppt_analysis_ref": copy.deepcopy(outputs["ppt.content_analyze"]),
            "page_count_adjustment": preferences["ppt_preferred_page_count"],
            "outline_lesson_plan": copy.deepcopy(lesson_plan),
        },
        "ppt.pages.generate": {
            "approved_outline_ref": copy.deepcopy(outputs["ppt.outline.generate"]),
            "page_style_preset": preferences["visual_style_key"],
            "pages_lesson_plan": copy.deepcopy(lesson_plan),
            "pages_material_evidence": copy.deepcopy(material),
        },
        "ppt.cover.prompt.generate": {
            "cover_candidate_count": ppt["cover"]["candidate_count"],
            "cover_style_preset": preferences["visual_style_key"],
            "cover_outline_context": copy.deepcopy(outputs["ppt.outline.generate"]),
            "cover_page_context": copy.deepcopy(cover_page),
        },
        "ppt.body_asset_prompts.generate": {
            "body_asset_scope": "all_missing",
            "body_page_specs": copy.deepcopy(pages),
            "body_style_contract": copy.deepcopy(ppt["style_contract"]),
        },
        "video.rough_storyboard.generate": {
            "rough_master_script_ref": copy.deepcopy(outputs["video.master_script.generate"]),
            "rough_pacing_preference": "balanced",
            "rough_selected_intro_ref": copy.deepcopy(selected_intro),
        },
        "video.style_master.prompt.generate": {
            "video_style_candidate_count": video["style_contract"]["candidate_count"],
            "video_style_preset": preferences["visual_style_key"],
            "style_master_script_ref": copy.deepcopy(outputs["video.master_script.generate"]),
            "style_rough_storyboard_ref": copy.deepcopy(outputs["video.rough_storyboard.generate"]),
        },
        "video.asset_inventory.generate": {
            "asset_reuse_policy": "deduplicate_base_identity",
            "inventory_master_script_ref": copy.deepcopy(outputs["video.master_script.generate"]),
            "inventory_rough_storyboard_ref": copy.deepcopy(
                outputs["video.rough_storyboard.generate"]
            ),
        },
        "video.asset_prompts.generate": {
            "video_asset_prompt_scope": "all_missing",
            "current_video_asset_inventory": copy.deepcopy(
                outputs["video.asset_inventory.generate"]
            ),
            "approved_video_style": copy.deepcopy(video["style_contract"]),
        },
    }
