"""Application service for the isolated video preproduction planning slice."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from apps.api.video_preproduction.fake import ScriptedDeterministicTextFake
from apps.api.video_preproduction.models import (
    AssetInventory,
    DurationRecommendation,
    ImagePrompt,
    MasterScript,
    PricingSnapshot,
    ProductionPlan,
    ReviewableVideoPreproductionPackage,
    RoughBeat,
    RoughStoryboard,
    TeacherConfirmation,
    ValidationReport,
    VideoAsset,
    VideoPreproductionRequest,
    VisualPlan,
)
from apps.api.video_preproduction.validator import validate_package
from workflow.content_package import canonical_json_sha256

AssetType = Literal["character", "scene", "prop", "creature"]


class VideoPreproductionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class VideoPreproductionService:
    def __init__(self, text_fake: ScriptedDeterministicTextFake) -> None:
        self._text_fake = text_fake

    def generate(self, request: VideoPreproductionRequest) -> ReviewableVideoPreproductionPackage:
        pricing = _require_pricing(request)
        recommendation = _recommend_duration(request, pricing)
        confirmation = _require_teacher_confirmation(request.teacher_confirmation, recommendation)
        master_script = self._text_fake.generate_master_script(
            request.intro_selection_snapshot,
            target_duration_seconds=recommendation.recommended_duration_seconds,
        )
        rough_storyboard = _build_rough_storyboard(master_script)
        visual_plan = _build_visual_plan(request.aspect_ratio, request.language)
        inventory = _build_asset_inventory(rough_storyboard)
        production_plan = _build_production_plan(inventory, visual_plan)
        package = ReviewableVideoPreproductionPackage(
            source_snapshot=request.intro_selection_snapshot,
            teacher_confirmation=confirmation,
            duration_recommendation=recommendation,
            master_script=master_script,
            rough_storyboard=rough_storyboard,
            visual_plan=visual_plan,
            asset_inventory=inventory,
            production_plan=production_plan,
            validation_report=ValidationReport(valid=True, errors=()),
            canonical_hash="0" * 64,
        )
        report = validate_package(package)
        if not report.valid:
            raise VideoPreproductionError("VIDEO_PREPRODUCTION_INVALID")
        finalized = package.model_copy(update={"validation_report": report})
        return finalized.model_copy(update={"canonical_hash": _canonical_hash(finalized)})


def _require_pricing(request: VideoPreproductionRequest) -> PricingSnapshot:
    if request.pricing_snapshot is None or not request.pricing_snapshot.version:
        raise VideoPreproductionError("PRICING_SNAPSHOT_REQUIRED")
    return request.pricing_snapshot


def _recommend_duration(
    request: VideoPreproductionRequest,
    pricing: PricingSnapshot,
) -> DurationRecommendation:
    story_seconds = min(30, 10 * (1 + len(request.intro_selection_snapshot.must_not_preteach)))
    preference_seconds = {"economy": -15, "balanced": 0, "quality": 15}[request.cost_preference]
    price_seconds = -15 if pricing.image_candidate_unit_price > Decimal("1.00") else 0
    duration = min(180, max(60, 60 + story_seconds + preference_seconds + price_seconds))
    asset_count = 5
    estimated_cost = pricing.image_candidate_unit_price * pricing.candidates_per_asset * asset_count
    rationale = (
        f"story boundary requires {story_seconds} additional seconds",
        f"cost preference adjustment is {preference_seconds} seconds",
        f"pricing snapshot {pricing.version} adjustment is {price_seconds} seconds",
    )
    return DurationRecommendation(
        recommended_duration_seconds=duration,
        estimated_cost=estimated_cost,
        pricing_version=pricing.version,
        currency=pricing.currency,
        rationale=rationale,
    )


def _require_teacher_confirmation(
    confirmation: TeacherConfirmation | None,
    recommendation: DurationRecommendation,
) -> TeacherConfirmation:
    if confirmation is None:
        raise VideoPreproductionError("TEACHER_CONFIRMATION_REQUIRED")
    if (
        confirmation.pricing_version != recommendation.pricing_version
        or confirmation.currency != recommendation.currency
        or confirmation.confirmed_duration_seconds != recommendation.recommended_duration_seconds
        or confirmation.confirmed_estimated_cost != recommendation.estimated_cost
    ):
        raise VideoPreproductionError("TEACHER_CONFIRMATION_REQUIRED")
    return confirmation


def _build_rough_storyboard(master_script: MasterScript) -> RoughStoryboard:
    asset_keys = (
        ("asset-robot", "asset-bay"),
        ("asset-box", "asset-slot"),
        ("asset-scan-light",),
    )
    beats = tuple(
        RoughBeat(
            beat_key=f"beat-{scene.position}",
            scene_key=scene.scene_key,
            position=scene.position,
            main_event=scene.visible_change,
            start_state=scene.start_state,
            end_state=scene.end_state,
            duration_seconds=scene.duration_seconds,
            asset_keys=asset_keys[scene.position - 1],
        )
        for scene in master_script.scenes
    )
    return RoughStoryboard(
        beats=beats,
        total_duration_seconds=sum(beat.duration_seconds for beat in beats),
    )


def _build_asset_inventory(storyboard: RoughStoryboard) -> AssetInventory:
    declarations: tuple[tuple[str, AssetType, str, str, tuple[str, ...]], ...] = (
        ("asset-robot", "character", "robot", "执行逐项核对。", ("beat-1",)),
        ("asset-bay", "scene", "supply-bay", "呈现补给舱空间。", ("beat-1",)),
        ("asset-box", "prop", "supply-box", "呈现待核对的补给盒。", ("beat-2",)),
        ("asset-slot", "prop", "supply-slot", "呈现一一对应的卡槽。", ("beat-2",)),
        ("asset-scan-light", "prop", "scan-light", "呈现课堂交接前的状态提示。", ("beat-3",)),
    )
    beat_keys = {beat.beat_key for beat in storyboard.beats}
    assets = tuple(
        VideoAsset(
            asset_key=asset_key,
            asset_type=asset_type,
            identity_key=identity_key,
            purpose=purpose,
            source_beat_keys=source_beat_keys,
        )
        for asset_key, asset_type, identity_key, purpose, source_beat_keys in declarations
        if set(source_beat_keys) <= beat_keys
    )
    return AssetInventory(assets=assets)


def _build_visual_plan(
    aspect_ratio: Literal["16:9", "9:16"],
    language: Literal["zh-CN"],
) -> VisualPlan:
    return VisualPlan(
        aspect_ratio=aspect_ratio,
        language=language,
        consistency_principles=(
            "机器人、补给舱和补给盒保持同一造型比例与材质。",
            "每个资产独立构图, 使用清楚的承托面与接触阴影。",
        ),
        negative_constraints=("文字", "水印", "Logo", "额外主体"),
    )


def _build_production_plan(inventory: AssetInventory, visual_plan: VisualPlan) -> ProductionPlan:
    prompts = tuple(
        ImagePrompt(
            asset_key=asset.asset_key,
            prompt=(f"{asset.purpose} 独立构图, 保持教育短片视觉一致性, 无文字无水印。"),
            negative_constraints=visual_plan.negative_constraints,
            aspect_ratio=visual_plan.aspect_ratio,
        )
        for asset in inventory.assets
    )
    return ProductionPlan(kind="image_prompts_only", image_prompts=prompts)


def _canonical_hash(package: ReviewableVideoPreproductionPackage) -> str:
    payload = package.model_dump(mode="json", exclude={"canonical_hash"})
    return canonical_json_sha256(payload)
