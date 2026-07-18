"""Project golden video facts into exact non-provider node outputs."""

from __future__ import annotations

import copy
from typing import Any, cast

REQUIRED_SOURCE_FIELDS: dict[str, tuple[str, ...]] = {
    "video.style_master.prompt.generate": (
        "video.style_contract.request_key",
        "video.style_contract.subjects",
        "video.style_contract.candidate_count",
        "video.style_contract.target_slot",
    ),
    "video.asset_inventory.generate": (
        "video.asset_inventory.assets[*].identity_key",
        "video.asset_inventory.assets[*].framing_rule",
        "video.asset_inventory.deduplication_notes",
    ),
    "video.asset_prompts.generate": (
        "video.asset_image_prompt_package_key",
        "video.asset_image_prompts[*].prompt_item_key",
        "video.asset_image_prompts[*].consistency_key",
    ),
    "audio.plan.generate": (
        "video.audio_plan.tracks[*].volume_intent",
        "video.audio_plan.tracks[*].ducking_rules",
    ),
}


def _rename(source: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    return {target: copy.deepcopy(source[origin]) for target, origin in aliases.items()}


def _path_exists(source: dict[str, Any], path: str) -> bool:
    values: list[Any] = [source]
    for part in path.split("."):
        expand = part.endswith("[*]")
        key = part.removesuffix("[*]")
        next_values: list[Any] = []
        for value in values:
            if not isinstance(value, dict) or key not in value:
                return False
            child = value[key]
            if expand:
                if not isinstance(child, list) or not child:
                    return False
                next_values.extend(child)
            else:
                next_values.append(child)
        values = next_values
    return all(value is not None for value in values)


def find_golden_video_stage_output_gaps(
    case: dict[str, Any],
) -> dict[str, tuple[str, ...]]:
    """Return required aggregate facts missing from conditionally mapped nodes."""

    return {
        node_key: missing
        for node_key, paths in REQUIRED_SOURCE_FIELDS.items()
        if (missing := tuple(path for path in paths if not _path_exists(case, path)))
    }


def _master_scene(source: dict[str, Any]) -> dict[str, Any]:
    return _rename(
        source,
        {
            "master_scene_key": "scene_key",
            "master_scene_position": "position",
            "master_scene_purpose": "purpose",
            "master_scene_location": "location",
            "master_scene_subjects": "subjects",
            "master_visible_change": "visible_change",
            "master_actions": "actions",
            "master_narration": "narration",
            "master_dialogue": "dialogue",
            "master_sound_intent": "sound_intent",
            "master_start_state": "start_state",
            "master_end_state": "end_state",
            "master_scene_duration_seconds": "duration_seconds",
        },
    )


def _master_script_output(case: dict[str, Any]) -> dict[str, Any]:
    video = cast(dict[str, Any], case["video"])
    master = cast(dict[str, Any], video["master_script"])
    quality = cast(dict[str, Any], video["quality_expectations"])
    handoff = cast(dict[str, Any], master["handoff"])
    return {
        "master_script_key": master["master_script_key"],
        "master_selected_intro_option_key": master["selected_intro_option_key"],
        "master_title": master["title"],
        "narrative_purpose": master["narrative_purpose"],
        "complete_story": master["complete_story"],
        "master_scenes": [_master_scene(item) for item in master["scenes"]],
        "master_handoff": _rename(
            handoff,
            {
                "master_course_anchor": "course_anchor",
                "master_classroom_first_question": "classroom_first_question",
                "master_handoff_moment": "handoff_moment",
                "master_must_not_preteach": "must_not_preteach",
            },
        ),
        "master_duration_recommendation": _rename(
            master["duration_recommendation"],
            {
                "master_duration_mode": "duration_mode",
                "master_recommended_duration_seconds": "recommended_duration_seconds",
                "master_duration_reason": "duration_reason",
                "master_estimated_shot_count": "estimated_shot_count",
                "master_pricing_quote_required": "pricing_quote_required",
            },
        ),
        "master_target_duration_seconds": master["target_duration_seconds"],
        "master_script_quality": {
            key: copy.deepcopy(quality[key])
            for key in (
                "selected_intro_snapshot_preserved",
                "independent_story_complete_before_anchor",
                "only_final_shot_hands_off",
                "must_not_preteach_preserved",
            )
        },
    }


def _rough_storyboard_output(case: dict[str, Any]) -> dict[str, Any]:
    video = cast(dict[str, Any], case["video"])
    rough = cast(dict[str, Any], video["rough_storyboard"])
    master = cast(dict[str, Any], video["master_script"])
    beats = [
        _rename(
            item,
            {
                "rough_beat_key": "beat_key",
                "rough_scene_key": "scene_key",
                "rough_position": "position",
                "rough_primary_event": "primary_event",
                "rough_start_state": "start_state",
                "rough_end_state": "end_state",
                "rough_duration_seconds": "duration_seconds",
                "rough_asset_needs": "asset_needs",
                "rough_transition": "transition",
            },
        )
        for item in rough["beats"]
    ]
    return {
        "rough_storyboard_key": rough["rough_storyboard_key"],
        "rough_master_script_key": master["master_script_key"],
        "rough_beats": beats,
        "rough_total_duration_seconds": rough["total_duration_seconds"],
        "rough_storyboard_quality": {
            "positions_contiguous": [item["position"] for item in rough["beats"]]
            == list(range(1, len(beats) + 1)),
            "beat_duration_sum_matches_total": sum(
                item["duration_seconds"] for item in rough["beats"]
            )
            == rough["total_duration_seconds"],
            "master_duration_matches": rough["total_duration_seconds"]
            == master["target_duration_seconds"],
        },
    }


def _fine_shot(source: dict[str, Any]) -> dict[str, Any]:
    output = _rename(
        source,
        {
            "shot_key": "shot_key",
            "shot_scene_key": "scene_key",
            "shot_beat_key": "beat_key",
            "shot_position": "position",
            "shot_duration_seconds": "duration_seconds",
            "shot_visible_beat": "visible_beat",
            "shot_start_state": "start_state",
            "shot_end_state": "end_state",
            "shot_camera": "camera",
            "shot_asset_usages": "asset_usages",
            "shot_prompt_text": "prompt_text",
            "shot_negative_constraints": "negative_constraints",
            "shot_narration_placeholder": "narration",
            "shot_dialogue_placeholder": "dialogue",
            "shot_sound_intent": "sound_intent",
            "shot_continuity_locks": "continuity_locks",
        },
    )
    output["shot_action_timeline"] = {"steps": copy.deepcopy(source["action_timeline"])}
    return output


def _fine_storyboard_output(case: dict[str, Any]) -> dict[str, Any]:
    video = cast(dict[str, Any], case["video"])
    fine = cast(dict[str, Any], video["fine_storyboard"])
    master = cast(dict[str, Any], video["master_script"])
    quality = cast(dict[str, Any], video["quality_expectations"])
    shots = [_fine_shot(item) for item in fine["shots"]]
    return {
        "fine_storyboard_key": fine["fine_storyboard_key"],
        "fine_source_master_script_key": master["master_script_key"],
        "fine_target_duration_seconds": fine["target_duration_seconds"],
        "fine_shots": shots,
        "fine_storyboard_quality": {
            key: copy.deepcopy(quality[key])
            for key in (
                "only_final_shot_hands_off",
                "must_not_preteach_preserved",
                "shot_durations_within_6_to_30",
                "visual_continuity_required",
            )
        },
    }


def _style_master_output(case: dict[str, Any]) -> dict[str, Any]:
    style = cast(dict[str, Any], case["video"]["style_contract"])
    return {
        "style_master_request_key": style["request_key"],
        "style_master_subjects": style["subjects"],
        "style_master_medium": style["medium"],
        "style_master_design_rules": "\n".join((style["character_rules"], style["scene_rules"])),
        "style_master_palette_lighting": style["palette_and_lighting"],
        "style_master_camera_motion": style["camera_and_motion"],
        "style_master_aspect_ratio": style["aspect_ratio"],
        "style_master_negative_constraints": copy.deepcopy(style["negative_constraints"]),
        "style_master_candidate_count": style["candidate_count"],
        "style_master_target_slot": style["target_slot"],
    }


def _scene_to_beat_keys(video: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for beat in video["rough_storyboard"]["beats"]:
        result.setdefault(beat["scene_key"], []).append(beat["beat_key"])
    return result


def _asset_inventory_output(case: dict[str, Any]) -> dict[str, Any]:
    video = cast(dict[str, Any], case["video"])
    inventory = cast(dict[str, Any], video["asset_inventory"])
    scene_beats = _scene_to_beat_keys(video)
    assets = []
    for item in inventory["assets"]:
        assets.append(
            {
                "video_asset_key": item["asset_key"],
                "video_asset_type": item["asset_type"],
                "video_asset_name": item["name"],
                "video_asset_identity_key": item["identity_key"],
                "video_asset_source_scene_keys": copy.deepcopy(item["source_scene_keys"]),
                "video_asset_source_beat_keys": [
                    beat_key
                    for scene_key in item["source_scene_keys"]
                    for beat_key in scene_beats.get(scene_key, [])
                ],
                "video_asset_usage": item["usage"],
                "video_asset_description": item["identity"],
                "video_asset_framing_rule": item["framing_rule"],
                "video_asset_target_slot": item["target_slot"],
            }
        )
    categories = cast(dict[str, Any], inventory["categories"])
    return {
        "asset_inventory_key": inventory["asset_inventory_key"],
        "video_assets": assets,
        "asset_category_summary": {
            f"{category}_asset_keys": copy.deepcopy(categories[category])
            for category in ("character", "scene", "prop", "creature")
        },
        "asset_deduplication_notes": inventory["deduplication_notes"],
    }


def _asset_prompts_output(case: dict[str, Any]) -> dict[str, Any]:
    video = cast(dict[str, Any], case["video"])
    style = cast(dict[str, Any], video["style_contract"])
    inventory = cast(dict[str, Any], video["asset_inventory"])
    asset_types = {item["asset_key"]: item["asset_type"] for item in inventory["assets"]}
    prompts = cast(list[dict[str, Any]], video["asset_image_prompts"])
    items = [
        {
            "video_asset_item_key": item["prompt_item_key"],
            "video_asset_source_key": item["asset_key"],
            "video_asset_prompt_type": asset_types[item["asset_key"]],
            "video_asset_prompt_target_slot": item["target_slot"],
            "video_asset_prompt_text": item["prompt_text"],
            "video_asset_negative_constraints": copy.deepcopy(item["negative_constraints"]),
            "video_asset_prompt_aspect_ratio": style["aspect_ratio"],
            "video_asset_prompt_consistency_key": item["consistency_key"],
        }
        for item in prompts
    ]
    asset_keys = [item["asset_key"] for item in inventory["assets"]]
    prompt_keys = [item["asset_key"] for item in prompts]
    return {
        "video_asset_package_key": video["asset_image_prompt_package_key"],
        "video_style_contract_ref": style["style_key"],
        "video_asset_prompt_items": items,
        "video_asset_prompt_coverage": {
            "all_inventory_assets_covered_once": sorted(asset_keys) == sorted(prompt_keys)
            and len(prompt_keys) == len(set(prompt_keys)),
            "asset_order_preserved": asset_keys == prompt_keys,
        },
    }


def _audio_track(source: dict[str, Any]) -> dict[str, Any]:
    timeline = cast(dict[str, Any], source["timeline"])
    return {
        "audio_track_key": source["track_key"],
        "audio_track_kind": source["kind"],
        "audio_track_shot_key": source["shot_key"],
        "audio_timeline_range": copy.deepcopy(timeline),
        "audio_script_text": source["script_text"],
        "audio_voice_profile": source["voice_profile"],
        "audio_rate": source["speech_rate"],
        "audio_expected_duration_seconds": timeline["end_seconds"] - timeline["start_seconds"],
        "audio_volume_intent": source["volume_intent"],
        "audio_ducking_rules": copy.deepcopy(source["ducking_rules"]),
        "audio_subtitle_text": source["subtitle_text"],
        "audio_target_slot": source["target_slot"],
    }


def _audio_plan_output(case: dict[str, Any]) -> dict[str, Any]:
    video = cast(dict[str, Any], case["video"])
    master = cast(dict[str, Any], video["master_script"])
    audio = cast(dict[str, Any], video["audio_plan"])
    timeline = cast(dict[str, Any], video["timeline_expectations"])
    return {
        "audio_plan_key": audio["audio_plan_key"],
        "audio_source_master_script_key": master["master_script_key"],
        "audio_tracks": [_audio_track(item) for item in audio["tracks"]],
        "audio_mix_plan": {
            "rules": copy.deepcopy(audio["mix_rules"]),
            "total_duration_seconds": timeline["total_duration_seconds"],
            "shot_order": copy.deepcopy(timeline["shot_order"]),
        },
        "audio_plan_quality": {
            "audio_tracks_bound_to_shots_or_ranges": timeline[
                "audio_tracks_bound_to_shots_or_ranges"
            ],
            "subtitle_editable": timeline["subtitle_editable"],
        },
    }


def build_golden_video_stage_outputs(
    case: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build all video stage outputs supported by authoritative aggregate facts."""

    outputs = {
        "video.master_script.generate": _master_script_output(case),
        "video.rough_storyboard.generate": _rough_storyboard_output(case),
        "video.fine_storyboard.generate": _fine_storyboard_output(case),
    }
    gaps = find_golden_video_stage_output_gaps(case)
    conditional_builders = {
        "video.style_master.prompt.generate": _style_master_output,
        "video.asset_inventory.generate": _asset_inventory_output,
        "video.asset_prompts.generate": _asset_prompts_output,
        "audio.plan.generate": _audio_plan_output,
    }
    for node_key, builder in conditional_builders.items():
        if node_key not in gaps:
            outputs[node_key] = builder(case)
    return outputs
