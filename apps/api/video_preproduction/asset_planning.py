"""Derive and validate story-bound visual assets for video preproduction."""

from __future__ import annotations

from apps.api.video_preproduction.models import (
    AssetInventory,
    ImagePrompt,
    MasterScene,
    ProductionPlan,
    ReviewableVideoPreproductionPackage,
    RoughStoryboard,
    VideoAsset,
    VisualPlan,
)


def inventory_assets(inventory: AssetInventory) -> tuple[VideoAsset, ...]:
    return (*inventory.characters, *inventory.scenes, *inventory.props, *inventory.creatures)


def build_asset_inventory(
    scenes: tuple[MasterScene, ...],
    storyboard: RoughStoryboard,
) -> AssetInventory:
    requirements = {
        requirement.asset_key: requirement
        for scene in scenes
        for requirement in scene.asset_requirements
    }
    scene_requirements = {
        scene.scene_key: {item.asset_key for item in scene.asset_requirements} for scene in scenes
    }
    assets = tuple(
        VideoAsset(
            asset_key=requirement.asset_key,
            asset_type=requirement.asset_type,
            identity_key=requirement.identity_key,
            purpose=requirement.purpose,
            visual_description=requirement.visual_description,
            source_beat_keys=tuple(
                beat.beat_key
                for beat in storyboard.beats
                if requirement.asset_key in scene_requirements[beat.scene_key]
            ),
        )
        for requirement in requirements.values()
    )
    return AssetInventory(
        characters=tuple(asset for asset in assets if asset.asset_type == "character"),
        scenes=tuple(asset for asset in assets if asset.asset_type == "scene"),
        props=tuple(asset for asset in assets if asset.asset_type == "prop"),
        creatures=tuple(asset for asset in assets if asset.asset_type == "creature"),
    )


def build_production_plan(inventory: AssetInventory, visual: VisualPlan) -> ProductionPlan:
    prompts = tuple(
        ImagePrompt(
            asset_key=asset.asset_key,
            prompt=(
                f"{asset.visual_description}; purpose: {asset.purpose}. "
                "Isolated composition, consistent visual language, no text or watermark."
            ),
            negative_constraints=visual.negative_constraints,
            aspect_ratio=visual.aspect_ratio,
        )
        for asset in inventory_assets(inventory)
    )
    return ProductionPlan(kind="image_prompts_only", image_prompts=prompts)


def validate_assets_and_plan(
    package: ReviewableVideoPreproductionPackage,
    errors: list[str],
) -> None:
    inventory = package.asset_inventory
    _validate_asset_categories(inventory, errors)
    assets = inventory_assets(inventory)
    asset_keys = tuple(asset.asset_key for asset in assets)
    beat_links = {
        (beat.beat_key, asset_key)
        for beat in package.rough_storyboard.beats
        for asset_key in beat.asset_keys
    }
    source_links = {
        (beat_key, asset.asset_key) for asset in assets for beat_key in asset.source_beat_keys
    }
    if len(asset_keys) != len(set(asset_keys)):
        errors.append("asset inventory keys must be unique")
    beat_keys = {beat.beat_key for beat in package.rough_storyboard.beats}
    if any(beat_key not in beat_keys for beat_key, _ in source_links):
        errors.append("asset source references an unknown beat")
    if any(asset_key not in set(asset_keys) for _, asset_key in beat_links):
        errors.append("rough beat references an unknown asset")
    if beat_links != source_links:
        errors.append("asset source and beat asset references must match exactly")
    _validate_assets_match_master(package, assets, errors)
    _validate_prompts(package, asset_keys, errors)


def _validate_asset_categories(inventory: AssetInventory, errors: list[str]) -> None:
    categories = (
        (inventory.characters, "character"),
        (inventory.scenes, "scene"),
        (inventory.props, "prop"),
        (inventory.creatures, "creature"),
    )
    if any(asset.asset_type != expected for assets, expected in categories for asset in assets):
        errors.append("asset category container does not match asset type")


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
    assets_by_key = {asset.asset_key: asset for asset in inventory_assets(package.asset_inventory)}
    for prompt in prompts:
        if prompt.aspect_ratio != package.visual_plan.aspect_ratio:
            errors.append("image prompts must use the visual plan aspect ratio")
        if not set(package.visual_plan.negative_constraints) <= set(prompt.negative_constraints):
            errors.append("image prompts must retain visual plan negative constraints")
        asset = assets_by_key.get(prompt.asset_key)
        if asset is not None and (
            asset.visual_description not in prompt.prompt or asset.purpose not in prompt.prompt
        ):
            errors.append("image prompts must retain asset visual semantics")
    if package.production_plan.media_operations:
        errors.append("preproduction package must not invoke media operations")


def _validate_assets_match_master(
    package: ReviewableVideoPreproductionPackage,
    assets: tuple[VideoAsset, ...],
    errors: list[str],
) -> None:
    requirements = {
        item.asset_key: item
        for scene in package.master_script.scenes
        for item in scene.asset_requirements
    }
    actual = {
        asset.asset_key: (
            asset.asset_type,
            asset.identity_key,
            asset.purpose,
            asset.visual_description,
        )
        for asset in assets
    }
    expected = {
        key: (item.asset_type, item.identity_key, item.purpose, item.visual_description)
        for key, item in requirements.items()
    }
    if actual != expected:
        errors.append("asset inventory must preserve master asset semantics")
