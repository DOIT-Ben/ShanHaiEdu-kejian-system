"""Pure validation and canonical hashing for video preproduction facts."""

from __future__ import annotations

from itertools import pairwise

from pydantic import BaseModel

from apps.api.video_preproduction.models import (
    ApprovalFact,
    IntroSelectionSnapshot,
    MasterScript,
    ReviewableVideoPreproductionPackage,
    RoughStoryboard,
    ValidationReport,
)
from workflow.content_package import canonical_json_sha256


def canonical_fact_hash(value: object) -> str:
    if not isinstance(value, BaseModel):
        raise TypeError("canonical facts must be Pydantic models")
    return canonical_json_sha256(value.model_dump(mode="json"))


def canonical_package_hash(package: ReviewableVideoPreproductionPackage) -> str:
    payload = package.model_dump(
        mode="json",
        exclude={"canonical_hash", "validation_report"},
    )
    return canonical_json_sha256(payload)


def validate_approval(
    approval: ApprovalFact,
    *,
    kind: str,
    key: str,
    value: object,
) -> tuple[str, ...]:
    errors: list[str] = []
    if approval.subject_kind != kind or approval.subject_key != key:
        errors.append("approval subject does not match")
    if approval.subject_hash != canonical_fact_hash(value):
        errors.append("approval hash does not match")
    return tuple(errors)


def validate_master_script(
    snapshot: IntroSelectionSnapshot,
    master: MasterScript,
) -> tuple[str, ...]:
    errors: list[str] = []
    if (
        master.selected_intro_snapshot_id != snapshot.snapshot_id
        or master.selected_intro_snapshot_version != snapshot.version
        or master.selected_intro_option_key != snapshot.option_key
    ):
        errors.append("master script snapshot identity does not match")
    if master.creative_concept != snapshot.creative_concept:
        errors.append("master script creative concept does not match")
    if master.course_anchor != snapshot.course_anchor:
        errors.append("master script course anchor does not match")
    _validate_master_structure(snapshot, master, errors)
    return tuple(errors)


def validate_rough_storyboard(
    master: MasterScript,
    rough: RoughStoryboard,
) -> tuple[str, ...]:
    errors: list[str] = []
    if rough.source_master_script_key != master.master_script_key:
        errors.append("rough storyboard master script identity does not match")
    _validate_positions(
        tuple(beat.position for beat in rough.beats),
        "rough beat positions must be unique and contiguous",
        errors,
    )
    scenes = {scene.scene_key: scene for scene in master.scenes}
    for beat in rough.beats:
        scene = scenes.get(beat.scene_key)
        if scene is None:
            errors.append("rough beat references an unknown scene")
        elif (beat.start_state, beat.end_state) != (scene.start_state, scene.end_state):
            errors.append("rough beat states must match the source scene")
    _validate_continuity(
        tuple((beat.start_state, beat.end_state) for beat in rough.beats),
        "rough beat states must be continuous",
        errors,
    )
    if sum(beat.duration_seconds for beat in rough.beats) != master.target_duration_seconds:
        errors.append("rough storyboard duration must equal the master script duration")
    return tuple(errors)


def validate_package(package: ReviewableVideoPreproductionPackage) -> ValidationReport:
    errors = list(validate_master_script(package.source_snapshot, package.master_script))
    errors.extend(validate_rough_storyboard(package.master_script, package.rough_storyboard))
    errors.extend(
        validate_approval(
            package.master_script_approval,
            kind="master_script",
            key=package.master_script.master_script_key,
            value=package.master_script,
        )
    )
    errors.extend(
        validate_approval(
            package.rough_storyboard_approval,
            kind="rough_storyboard",
            key=package.rough_storyboard.rough_storyboard_key,
            value=package.rough_storyboard,
        )
    )
    _validate_duration(package, errors)
    _validate_assets_and_plan(package, errors)
    if canonical_package_hash(package) != package.canonical_hash:
        errors.append("canonical hash does not match package content")
    return ValidationReport(valid=not errors, errors=tuple(dict.fromkeys(errors)))


def _validate_master_structure(
    snapshot: IntroSelectionSnapshot,
    master: MasterScript,
    errors: list[str],
) -> None:
    _validate_positions(
        tuple(scene.position for scene in master.scenes),
        "master scene positions must be unique and contiguous",
        errors,
    )
    if len({scene.scene_key for scene in master.scenes}) != len(master.scenes):
        errors.append("master scene keys must be unique")
    _validate_continuity(
        tuple((scene.start_state, scene.end_state) for scene in master.scenes),
        "master scene states must be continuous",
        errors,
    )
    if master.scenes[-1].end_state != snapshot.handoff_moment or not master.ends_at_handoff:
        errors.append("master script must end at the selected handoff moment")
    if snapshot.course_anchor not in master.complete_story:
        errors.append("master story must contain the selected course anchor")
    for forbidden in snapshot.must_not_preteach:
        if forbidden in master.complete_story:
            errors.append(f"master script must not preteach: {forbidden}")


def _validate_duration(
    package: ReviewableVideoPreproductionPackage,
    errors: list[str],
) -> None:
    target = package.master_script.target_duration_seconds
    if sum(scene.duration_seconds for scene in package.master_script.scenes) != target:
        errors.append("master scene durations must equal the target duration")
    if package.rough_storyboard.total_duration_seconds != target:
        errors.append("rough storyboard duration must equal the master script duration")


def _validate_assets_and_plan(
    package: ReviewableVideoPreproductionPackage,
    errors: list[str],
) -> None:
    assets = package.asset_inventory.assets
    asset_keys = tuple(asset.asset_key for asset in assets)
    beat_keys = {beat.beat_key for beat in package.rough_storyboard.beats}
    beat_asset_links = {
        (beat.beat_key, asset_key)
        for beat in package.rough_storyboard.beats
        for asset_key in beat.asset_keys
    }
    if {asset.asset_type for asset in assets} != {"character", "scene", "prop", "creature"}:
        errors.append("asset inventory must contain all four asset categories")
    if len(asset_keys) != len(set(asset_keys)):
        errors.append("asset inventory keys must be unique")
    for asset in assets:
        if not set(asset.source_beat_keys) <= beat_keys:
            errors.append("asset source references an unknown beat")
        if any(
            (beat_key, asset.asset_key) not in beat_asset_links
            for beat_key in asset.source_beat_keys
        ):
            errors.append("asset source and beat asset references must agree")
    if any(asset_key not in set(asset_keys) for _, asset_key in beat_asset_links):
        errors.append("rough beat references an unknown asset")
    _validate_prompts(package, asset_keys, errors)


def _validate_prompts(
    package: ReviewableVideoPreproductionPackage,
    asset_keys: tuple[str, ...],
    errors: list[str],
) -> None:
    prompts = package.production_plan.image_prompts
    prompt_keys = tuple(prompt.asset_key for prompt in prompts)
    if len(prompt_keys) != len(set(prompt_keys)):
        errors.append("image prompt asset keys must be unique")
    if set(prompt_keys) != set(asset_keys):
        errors.append("image prompts must cover each inventory asset exactly once")
    for prompt in prompts:
        if prompt.aspect_ratio != package.visual_plan.aspect_ratio:
            errors.append("image prompts must use the visual plan aspect ratio")
        if not set(package.visual_plan.negative_constraints) <= set(prompt.negative_constraints):
            errors.append("image prompts must retain visual plan negative constraints")
    if package.production_plan.media_operations:
        errors.append("preproduction package must not invoke media operations")


def _validate_positions(
    positions: tuple[int, ...],
    message: str,
    errors: list[str],
) -> None:
    if sorted(positions) != list(range(1, len(positions) + 1)):
        errors.append(message)


def _validate_continuity(
    states: tuple[tuple[str, str], ...],
    message: str,
    errors: list[str],
) -> None:
    if any(previous[1] != current[0] for previous, current in pairwise(states)):
        errors.append(message)
