"""Validate video and delivery invariants in the golden courseware case."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, NoReturn, cast

Fail = Callable[[str, str], NoReturn]
FORBIDDEN_VIDEO_SOURCES = {
    "lesson_plan.approved_version",
    "material.approved_parse",
    "ppt_outline.approved_version",
}
REQUIRED_DELIVERY_ARTIFACT_FAMILIES = {
    "lesson_plan_docx_pdf",
    "intro_option_appendix",
    "editable_pptx_preview",
    "final_video_subtitles_audio_plan",
    "quality_reports",
    "file_manifest",
}


def _require_unique(values: list[object], *, code: str, label: str, fail: Fail) -> None:
    serialized = [json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values]
    if len(serialized) != len(set(serialized)):
        fail(code, f"duplicate {label}")


def _validate_master(
    case: dict[str, Any], video: dict[str, Any], *, fail: Fail
) -> tuple[int, set[str]]:
    selection = cast(dict[str, Any], case["intro_selection"])
    if video["selected_intro_option_key"] != selection["option_key"]:
        fail("GOLDEN_VIDEO_SOURCE_INVALID", "video must use the selected intro option")
    policy = cast(dict[str, Any], video["source_policy"])
    if policy["allowed_sources"] != ["intro_selection.snapshot"]:
        fail("GOLDEN_VIDEO_CONTEXT_INVALID", "video has more than the selected snapshot")
    if not FORBIDDEN_VIDEO_SOURCES.issubset(set(cast(list[str], policy["forbidden_sources"]))):
        fail("GOLDEN_VIDEO_CONTEXT_INVALID", "video forbidden sources are incomplete")

    snapshot = cast(dict[str, Any], selection["snapshot"])
    master = cast(dict[str, Any], video["master_script"])
    if master["selected_intro_option_key"] != snapshot["option_key"]:
        fail("GOLDEN_VIDEO_MASTER_SOURCE_INVALID", "master script source is inconsistent")
    handoff = cast(dict[str, Any], master["handoff"])
    for key in ("course_anchor", "classroom_first_question", "handoff_moment"):
        if handoff[key] != snapshot[key]:
            fail("GOLDEN_VIDEO_HANDOFF_INVALID", f"master script changed {key}")
    if handoff["must_not_preteach"] != snapshot["must_not_preteach"]:
        fail("GOLDEN_VIDEO_HANDOFF_INVALID", "master script changed must_not_preteach")

    target = cast(int, master["target_duration_seconds"])
    preferences = cast(dict[str, Any], case["teacher_preferences"])
    recommendation = cast(dict[str, Any], master["duration_recommendation"])
    if not 60 <= target <= 180:
        fail("GOLDEN_VIDEO_DURATION_INVALID", "video duration must be 60 to 180 seconds")
    if recommendation["duration_mode"] != preferences["video_duration_mode"]:
        fail("GOLDEN_VIDEO_DURATION_INVALID", "video duration mode differs")
    if recommendation["recommended_duration_seconds"] != target:
        fail("GOLDEN_VIDEO_DURATION_INVALID", "recommended and confirmed duration differ")
    if target != preferences["video_target_duration_seconds"]:
        fail("GOLDEN_VIDEO_DURATION_INVALID", "golden duration differs from expected target")
    if not recommendation["duration_reason"] or recommendation["estimated_shot_count"] < 2:
        fail("GOLDEN_VIDEO_DURATION_INVALID", "video duration recommendation is incomplete")
    if recommendation["pricing_quote_required"] is not True:
        fail("GOLDEN_VIDEO_PRICING_INVALID", "server pricing quote must precede approval")
    scenes = cast(list[dict[str, Any]], master["scenes"])
    _require_unique(
        [scene["scene_key"] for scene in scenes],
        code="GOLDEN_VIDEO_SCENE_KEY_DUPLICATE",
        label="video scene key",
        fail=fail,
    )
    return target, {scene["scene_key"] for scene in scenes}


def _validate_rough(
    video: dict[str, Any], target: int, scene_keys: set[str], *, fail: Fail
) -> set[str]:
    rough = cast(dict[str, Any], video["rough_storyboard"])
    beats = cast(list[dict[str, Any]], rough["beats"])
    if sum(cast(int, beat["duration_seconds"]) for beat in beats) != target:
        fail("GOLDEN_VIDEO_ROUGH_DURATION_INVALID", "rough storyboard duration differs")
    if rough["total_duration_seconds"] != target:
        fail("GOLDEN_VIDEO_ROUGH_DURATION_INVALID", "rough total duration differs")
    _require_unique(
        [beat["beat_key"] for beat in beats],
        code="GOLDEN_VIDEO_BEAT_KEY_DUPLICATE",
        label="video beat key",
        fail=fail,
    )
    if not {beat["scene_key"] for beat in beats}.issubset(scene_keys):
        fail("GOLDEN_VIDEO_BEAT_SOURCE_INVALID", "rough beat references a missing scene")
    return {beat["beat_key"] for beat in beats}


def _validate_assets(video: dict[str, Any], scene_keys: set[str], *, fail: Fail) -> set[str]:
    inventory = cast(dict[str, Any], video["asset_inventory"])
    categories = cast(dict[str, list[str]], inventory["categories"])
    if set(categories) != {"character", "scene", "prop", "creature"}:
        fail("GOLDEN_VIDEO_ASSET_CATEGORIES_INVALID", "asset categories must be explicit")
    assets = cast(list[dict[str, Any]], inventory["assets"])
    for key, code, label in (
        ("asset_key", "GOLDEN_VIDEO_ASSET_KEY_DUPLICATE", "video asset key"),
        ("identity", "GOLDEN_VIDEO_ASSET_IDENTITY_DUPLICATE", "video asset identity"),
        ("target_slot", "GOLDEN_VIDEO_ASSET_SLOT_DUPLICATE", "video asset target slot"),
    ):
        _require_unique([asset[key] for asset in assets], code=code, label=label, fail=fail)
    asset_keys = {asset["asset_key"] for asset in assets}
    for category, category_keys in categories.items():
        expected = {asset["asset_key"] for asset in assets if asset["asset_type"] == category}
        if len(category_keys) != len(set(category_keys)) or set(category_keys) != expected:
            fail("GOLDEN_VIDEO_ASSET_CATEGORIES_INVALID", "asset category refs are inconsistent")
    if any(
        not set(cast(list[str], asset["source_scene_keys"])).issubset(scene_keys)
        for asset in assets
    ):
        fail("GOLDEN_VIDEO_ASSET_SOURCE_INVALID", "asset references a missing scene")

    prompts = cast(list[dict[str, Any]], video["asset_image_prompts"])
    _require_unique(
        [item["asset_key"] for item in prompts],
        code="GOLDEN_VIDEO_ASSET_PROMPT_DUPLICATE",
        label="video asset prompt key",
        fail=fail,
    )
    if {item["asset_key"] for item in prompts} != asset_keys:
        fail("GOLDEN_VIDEO_ASSET_PROMPTS_INVALID", "every asset needs one image prompt")
    slots = {asset["asset_key"]: asset["target_slot"] for asset in assets}
    if any(item["target_slot"] != slots[item["asset_key"]] for item in prompts):
        fail("GOLDEN_VIDEO_ASSET_PROMPTS_INVALID", "asset prompt changed its target slot")
    return asset_keys


def _validate_shots(
    video: dict[str, Any],
    target: int,
    scene_keys: set[str],
    beat_keys: set[str],
    asset_keys: set[str],
    *,
    fail: Fail,
) -> dict[str, str]:
    fine = cast(dict[str, Any], video["fine_storyboard"])
    shots = cast(list[dict[str, Any]], fine["shots"])
    if [shot["position"] for shot in shots] != list(range(1, len(shots) + 1)):
        fail("GOLDEN_VIDEO_SHOT_POSITION_INVALID", "shot positions must be contiguous")
    _require_unique(
        [shot["shot_key"] for shot in shots],
        code="GOLDEN_VIDEO_SHOT_KEY_DUPLICATE",
        label="shot key",
        fail=fail,
    )
    if any(not 6 <= shot["duration_seconds"] <= 30 for shot in shots):
        fail("GOLDEN_VIDEO_SHOT_DURATION_INVALID", "shot duration must be 6 to 30 seconds")
    if sum(cast(int, shot["duration_seconds"]) for shot in shots) != target:
        fail("GOLDEN_VIDEO_SHOT_DURATION_INVALID", "shot duration sum differs from target")
    for shot in shots:
        if shot["scene_key"] not in scene_keys or shot["beat_key"] not in beat_keys:
            fail("GOLDEN_VIDEO_SHOT_SOURCE_INVALID", "shot references a missing scene or beat")
        usages = cast(list[dict[str, Any]], shot["asset_usages"])
        if not {usage["asset_key"] for usage in usages}.issubset(asset_keys):
            fail("GOLDEN_VIDEO_SHOT_ASSET_INVALID", "shot references missing asset")
    if any(shot.get("handoff_marker") for shot in shots[:-1]) or not shots[-1].get(
        "handoff_marker"
    ):
        fail("GOLDEN_VIDEO_HANDOFF_INVALID", "only the final shot may hand off")
    return {cast(str, shot["shot_key"]): cast(str, shot["beat_key"]) for shot in shots}


def _validate_clips_audio(
    video: dict[str, Any], target: int, shot_to_beat: dict[str, str], *, fail: Fail
) -> None:
    shot_keys = set(shot_to_beat)
    clips = cast(list[dict[str, Any]], video["clip_expectations"])
    _require_unique(
        [item["shot_key"] for item in clips],
        code="GOLDEN_VIDEO_CLIP_EXPECTATION_DUPLICATE",
        label="clip expectation shot key",
        fail=fail,
    )
    if {item["shot_key"] for item in clips} != shot_keys:
        fail("GOLDEN_VIDEO_CLIP_EXPECTATION_INVALID", "clip expectations must cover shots")
    if not all(item["formal_clip_after_adopt_and_save"] for item in clips):
        fail("GOLDEN_VIDEO_CLIP_EXPECTATION_INVALID", "candidate cannot be a formal clip")
    timeline = cast(dict[str, Any], video["timeline_expectations"])
    if timeline["shot_order"] != [item["shot_key"] for item in clips]:
        fail("GOLDEN_VIDEO_TIMELINE_INVALID", "timeline shot order differs")
    if timeline["total_duration_seconds"] != target:
        fail("GOLDEN_VIDEO_TIMELINE_INVALID", "timeline duration differs")

    tracks = cast(list[dict[str, Any]], video["audio_plan"]["tracks"])
    if not tracks:
        fail("GOLDEN_AUDIO_TRACKS_MISSING", "audio plan must contain tracks")
    for key, code, label in (
        ("track_key", "GOLDEN_AUDIO_TRACK_KEY_DUPLICATE", "audio track key"),
        ("target_slot", "GOLDEN_AUDIO_TARGET_SLOT_DUPLICATE", "audio target slot"),
    ):
        _require_unique([track[key] for track in tracks], code=code, label=label, fail=fail)
    if not {"narration", "sound_effect", "music"}.issubset(
        {cast(str, track["kind"]) for track in tracks}
    ):
        fail("GOLDEN_AUDIO_KIND_INCOMPLETE", "golden audio plan misses a required track kind")
    narration_shots: set[str] = set()
    for track in tracks:
        shot_key = track.get("shot_key")
        if shot_key is not None and shot_key not in shot_keys:
            fail("GOLDEN_AUDIO_SHOT_REF_INVALID", "audio track references missing shot")
        if track["kind"] in {"narration", "dialogue"} and shot_key is not None:
            narration_shots.add(cast(str, shot_key))
            if not track["subtitle_text"]:
                fail("GOLDEN_AUDIO_SUBTITLE_MISSING", "spoken track needs editable subtitles")
        track_range = cast(dict[str, Any], track["timeline"])
        if not (0 <= track_range["start_seconds"] < track_range["end_seconds"] <= target):
            fail("GOLDEN_AUDIO_TIMELINE_INVALID", "audio track leaves the video timeline")
    narration_beats = {shot_to_beat[shot_key] for shot_key in narration_shots}
    if narration_beats != set(shot_to_beat.values()):
        fail("GOLDEN_AUDIO_BEAT_COVERAGE_INVALID", "spoken audio must cover every story beat")


def validate_golden_video(case: dict[str, Any], *, fail: Fail) -> None:
    video = cast(dict[str, Any], case["video"])
    target, scene_keys = _validate_master(case, video, fail=fail)
    beat_keys = _validate_rough(video, target, scene_keys, fail=fail)
    asset_keys = _validate_assets(video, scene_keys, fail=fail)
    shot_to_beat = _validate_shots(video, target, scene_keys, beat_keys, asset_keys, fail=fail)
    _validate_clips_audio(video, target, shot_to_beat, fail=fail)


def validate_golden_delivery(case: dict[str, Any], *, fail: Fail) -> None:
    delivery = cast(dict[str, Any], case["delivery_expectations"])
    expected_keys = {
        "enabled_branches",
        "required_artifact_families",
        "golden_fixture_claim",
        "ordinary_ci_provider_policy",
        "milestone_exit_provider_policy",
    }
    if set(delivery) != expected_keys:
        fail("GOLDEN_DELIVERY_EXPECTATION_INVALID", "delivery expectations are incomplete")
    project = cast(dict[str, Any], case["project"])
    if delivery["enabled_branches"] != project["enabled_branches"]:
        fail("GOLDEN_DELIVERY_BRANCH_INVALID", "delivery branches differ from the project")
    if set(cast(list[str], delivery["required_artifact_families"])) != (
        REQUIRED_DELIVERY_ARTIFACT_FAMILIES
    ):
        fail("GOLDEN_DELIVERY_ARTIFACT_INVALID", "delivery artifact families are incomplete")
    if delivery["ordinary_ci_provider_policy"] != "deterministic_fake_only":
        fail("GOLDEN_DELIVERY_PROVIDER_POLICY_INVALID", "ordinary CI must use deterministic fakes")
    if delivery["milestone_exit_provider_policy"] != "real_text_image_video_smoke_tts_deferred":
        fail(
            "GOLDEN_DELIVERY_PROVIDER_POLICY_INVALID",
            "current milestone must defer TTS while preserving real media smokes",
        )
