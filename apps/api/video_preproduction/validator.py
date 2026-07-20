"""Pure business validation for a reviewable video preproduction package."""

from __future__ import annotations

from apps.api.video_preproduction.models import (
    ReviewableVideoPreproductionPackage,
    ValidationReport,
)


def validate_package(package: ReviewableVideoPreproductionPackage) -> ValidationReport:
    errors: list[str] = []
    _validate_duration(package, errors)
    _validate_handoff_and_boundary(package, errors)
    _validate_visual_plan(package, errors)
    _validate_assets_and_plan(package, errors)
    return ValidationReport(valid=not errors, errors=tuple(errors))


def _validate_duration(package: ReviewableVideoPreproductionPackage, errors: list[str]) -> None:
    target = package.master_script.target_duration_seconds
    if not 60 <= target <= 180:
        errors.append("master script duration must be within 60 to 180 seconds")
    if package.rough_storyboard.total_duration_seconds != target:
        errors.append("rough storyboard duration must equal the master script duration")
    if sum(beat.duration_seconds for beat in package.rough_storyboard.beats) != target:
        errors.append("rough storyboard beat durations must equal the master script duration")
    if sum(scene.duration_seconds for scene in package.master_script.scenes) != target:
        errors.append("master scene durations must equal the target duration")


def _validate_handoff_and_boundary(
    package: ReviewableVideoPreproductionPackage,
    errors: list[str],
) -> None:
    snapshot = package.source_snapshot
    if not package.master_script.ends_at_handoff:
        errors.append("master script must end at the selected handoff moment")
    if package.master_script.scenes[-1].end_state != snapshot.handoff_moment:
        errors.append("final scene must end at the selected handoff moment")
    story = package.master_script.complete_story
    for forbidden in snapshot.must_not_preteach:
        if forbidden in story:
            errors.append(f"master script must not preteach: {forbidden}")


def _validate_assets_and_plan(
    package: ReviewableVideoPreproductionPackage,
    errors: list[str],
) -> None:
    asset_keys = tuple(asset.asset_key for asset in package.asset_inventory.assets)
    prompt_keys = tuple(prompt.asset_key for prompt in package.production_plan.image_prompts)
    if len(asset_keys) != len(set(asset_keys)):
        errors.append("asset inventory keys must be unique")
    if set(prompt_keys) != set(asset_keys):
        errors.append("image prompts must cover each inventory asset exactly once")
    if package.production_plan.kind != "image_prompts_only":
        errors.append("preproduction package may only contain image prompts")
    if package.production_plan.media_operations:
        errors.append("preproduction package must not invoke media operations")


def _validate_visual_plan(
    package: ReviewableVideoPreproductionPackage,
    errors: list[str],
) -> None:
    plan = package.visual_plan
    if plan.aspect_ratio != package.production_plan.image_prompts[0].aspect_ratio:
        errors.append("image prompts must use the visual plan aspect ratio")
    if not set(plan.negative_constraints) <= set(
        package.production_plan.image_prompts[0].negative_constraints
    ):
        errors.append("image prompts must retain visual plan negative constraints")
