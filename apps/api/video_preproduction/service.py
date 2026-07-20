"""Stage-gated application service for isolated video preproduction planning."""

from __future__ import annotations

from decimal import Decimal

from apps.api.video_preproduction.fake import ScriptedDeterministicTextFake
from apps.api.video_preproduction.models import (
    ApprovalFact,
    AssetInventory,
    DurationRecommendation,
    ImagePrompt,
    PricingSnapshot,
    ProductionPlan,
    ReviewableMasterScriptStage,
    ReviewableRoughStoryboardStage,
    ReviewableVideoPreproductionPackage,
    RoughBeat,
    RoughStoryboard,
    StoryComplexity,
    TeacherConfirmation,
    ValidationReport,
    VideoAsset,
    VideoPreproductionRequest,
    VisualPlan,
)
from apps.api.video_preproduction.validator import (
    canonical_package_hash,
    validate_approval,
    validate_master_script,
    validate_package,
    validate_rough_storyboard,
)


class VideoPreproductionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class VideoPreproductionService:
    def __init__(self, text_fake: ScriptedDeterministicTextFake) -> None:
        self._text_fake = text_fake

    def recommend(self, request: VideoPreproductionRequest) -> DurationRecommendation:
        pricing = _require_pricing(request)
        complexity = _story_complexity(request)
        preference_seconds = {"economy": -10, "balanced": 0, "quality": 10}[request.cost_preference]
        price_seconds = -10 if pricing.image_candidate_unit_price > Decimal("1.00") else 0
        duration = min(
            180,
            max(60, complexity.scene_count * 25 + preference_seconds + price_seconds),
        )
        cost = (
            pricing.image_candidate_unit_price
            * pricing.candidates_per_asset
            * complexity.estimated_asset_count
        )
        return DurationRecommendation(
            recommended_duration_seconds=duration,
            estimated_cost=cost,
            pricing_version=pricing.version,
            currency=pricing.currency,
            story_complexity=complexity,
            rationale=(
                f"creative concept chars: {complexity.creative_concept_chars}",
                f"course anchor chars: {complexity.course_anchor_chars}",
                f"scene and beat count: {complexity.scene_count}",
                f"pricing snapshot: {pricing.version}",
            ),
        )

    def generate_master_script(
        self,
        request: VideoPreproductionRequest,
        recommendation: DurationRecommendation,
        confirmation: TeacherConfirmation | None,
    ) -> ReviewableMasterScriptStage:
        if recommendation != self.recommend(request):
            raise VideoPreproductionError("DURATION_RECOMMENDATION_STALE")
        confirmed = _require_confirmation(confirmation, recommendation)
        script = self._text_fake.generate_master_script(
            request.intro_selection_snapshot,
            target_duration_seconds=recommendation.recommended_duration_seconds,
            scene_count=recommendation.story_complexity.scene_count,
        )
        if validate_master_script(request.intro_selection_snapshot, script):
            raise VideoPreproductionError("VIDEO_MASTER_SCRIPT_INVALID")
        return ReviewableMasterScriptStage(
            source_snapshot=request.intro_selection_snapshot,
            teacher_confirmation=confirmed,
            duration_recommendation=recommendation,
            master_script=script,
        )

    def generate_rough_storyboard(
        self,
        master_stage: ReviewableMasterScriptStage,
        master_approval: ApprovalFact | None,
    ) -> ReviewableRoughStoryboardStage:
        approved = _require_approval(
            master_approval,
            kind="master_script",
            key=master_stage.master_script.master_script_key,
            value=master_stage.master_script,
            error_code="MASTER_SCRIPT_APPROVAL_REQUIRED",
        )
        rough = _build_rough_storyboard(master_stage)
        if validate_rough_storyboard(master_stage.master_script, rough):
            raise VideoPreproductionError("VIDEO_ROUGH_STORYBOARD_INVALID")
        return ReviewableRoughStoryboardStage(
            master_stage=master_stage,
            master_script_approval=approved,
            rough_storyboard=rough,
        )

    def generate_package(
        self,
        request: VideoPreproductionRequest,
        rough_stage: ReviewableRoughStoryboardStage,
        rough_approval: ApprovalFact | None,
    ) -> ReviewableVideoPreproductionPackage:
        approved = _require_approval(
            rough_approval,
            kind="rough_storyboard",
            key=rough_stage.rough_storyboard.rough_storyboard_key,
            value=rough_stage.rough_storyboard,
            error_code="ROUGH_STORYBOARD_APPROVAL_REQUIRED",
        )
        _require_stage_source(request, rough_stage)
        package = _build_package(request, rough_stage, approved)
        report = validate_package(package)
        if not report.valid:
            raise VideoPreproductionError("VIDEO_PREPRODUCTION_INVALID")
        return package.model_copy(update={"validation_report": report})


def _require_pricing(request: VideoPreproductionRequest) -> PricingSnapshot:
    if request.pricing_snapshot is None or not request.pricing_snapshot.version:
        raise VideoPreproductionError("PRICING_SNAPSHOT_REQUIRED")
    return request.pricing_snapshot


def _story_complexity(request: VideoPreproductionRequest) -> StoryComplexity:
    snapshot = request.intro_selection_snapshot
    creative_chars = len(snapshot.creative_concept.strip())
    anchor_chars = len(snapshot.course_anchor.strip())
    combined_chars = creative_chars + anchor_chars
    scene_count = min(6, max(3, 2 + (combined_chars + 79) // 80))
    return StoryComplexity(
        creative_concept_chars=creative_chars,
        course_anchor_chars=anchor_chars,
        scene_count=scene_count,
        beat_count=scene_count,
        estimated_asset_count=scene_count + 1,
    )


def _require_confirmation(
    confirmation: TeacherConfirmation | None,
    recommendation: DurationRecommendation,
) -> TeacherConfirmation:
    if confirmation is None or (
        confirmation.pricing_version != recommendation.pricing_version
        or confirmation.currency != recommendation.currency
        or confirmation.confirmed_duration_seconds != recommendation.recommended_duration_seconds
        or confirmation.confirmed_estimated_cost != recommendation.estimated_cost
    ):
        raise VideoPreproductionError("TEACHER_CONFIRMATION_REQUIRED")
    return confirmation


def _require_approval(
    approval: ApprovalFact | None,
    *,
    kind: str,
    key: str,
    value: object,
    error_code: str,
) -> ApprovalFact:
    if approval is None or validate_approval(approval, kind=kind, key=key, value=value):
        raise VideoPreproductionError(error_code)
    return approval


def _require_stage_source(
    request: VideoPreproductionRequest,
    rough_stage: ReviewableRoughStoryboardStage,
) -> None:
    master_stage = rough_stage.master_stage
    if (
        master_stage.source_snapshot != request.intro_selection_snapshot
        or master_stage.duration_recommendation
        != VideoPreproductionService(ScriptedDeterministicTextFake()).recommend(request)
    ):
        raise VideoPreproductionError("VIDEO_PREPRODUCTION_SOURCE_STALE")
    if validate_master_script(master_stage.source_snapshot, master_stage.master_script):
        raise VideoPreproductionError("VIDEO_MASTER_SCRIPT_INVALID")
    if validate_rough_storyboard(master_stage.master_script, rough_stage.rough_storyboard):
        raise VideoPreproductionError("VIDEO_ROUGH_STORYBOARD_INVALID")
    if validate_approval(
        rough_stage.master_script_approval,
        kind="master_script",
        key=master_stage.master_script.master_script_key,
        value=master_stage.master_script,
    ):
        raise VideoPreproductionError("MASTER_SCRIPT_APPROVAL_REQUIRED")


def _build_rough_storyboard(master_stage: ReviewableMasterScriptStage) -> RoughStoryboard:
    master = master_stage.master_script
    beats = tuple(
        RoughBeat(
            beat_key=f"beat-{scene.position}",
            scene_key=scene.scene_key,
            position=scene.position,
            main_event=scene.visible_change,
            start_state=scene.start_state,
            end_state=scene.end_state,
            duration_seconds=scene.duration_seconds,
            asset_keys=_beat_asset_keys(scene.position),
        )
        for scene in master.scenes
    )
    return RoughStoryboard(
        rough_storyboard_key=f"rough-{master.master_script_key}",
        source_master_script_key=master.master_script_key,
        beats=beats,
        total_duration_seconds=sum(beat.duration_seconds for beat in beats),
    )


def _beat_asset_keys(position: int) -> tuple[str, ...]:
    if position == 1:
        return "asset-character", "asset-scene"
    if position == 2:
        return ("asset-prop",)
    if position == 3:
        return ("asset-creature",)
    return (f"asset-scene-{position}",)


def _build_package(
    request: VideoPreproductionRequest,
    rough_stage: ReviewableRoughStoryboardStage,
    rough_approval: ApprovalFact,
) -> ReviewableVideoPreproductionPackage:
    master_stage = rough_stage.master_stage
    visual = _build_visual_plan(request)
    inventory = _build_asset_inventory(rough_stage.rough_storyboard)
    plan = _build_production_plan(inventory, visual)
    package = ReviewableVideoPreproductionPackage(
        source_snapshot=master_stage.source_snapshot,
        teacher_confirmation=master_stage.teacher_confirmation,
        duration_recommendation=master_stage.duration_recommendation,
        master_script=master_stage.master_script,
        master_script_approval=rough_stage.master_script_approval,
        rough_storyboard=rough_stage.rough_storyboard,
        rough_storyboard_approval=rough_approval,
        visual_plan=visual,
        asset_inventory=inventory,
        production_plan=plan,
        validation_report=ValidationReport(valid=True, errors=()),
        canonical_hash="0" * 64,
    )
    return package.model_copy(update={"canonical_hash": canonical_package_hash(package)})


def _build_visual_plan(request: VideoPreproductionRequest) -> VisualPlan:
    return VisualPlan(
        aspect_ratio=request.aspect_ratio,
        language=request.language,
        consistency_principles=(
            "主体、场景、道具和生物保持同一造型比例与材质。",
            "每个资产独立构图, 使用清楚的承托面与接触阴影。",
        ),
        negative_constraints=("文字", "水印", "Logo", "额外主体"),
    )


def _build_asset_inventory(storyboard: RoughStoryboard) -> AssetInventory:
    assets = [
        VideoAsset(
            asset_key="asset-character",
            asset_type="character",
            identity_key="story-character",
            purpose="承载故事主要行动。",
            source_beat_keys=("beat-1",),
        ),
        VideoAsset(
            asset_key="asset-scene",
            asset_type="scene",
            identity_key="story-scene",
            purpose="呈现故事发生空间。",
            source_beat_keys=("beat-1",),
        ),
        VideoAsset(
            asset_key="asset-prop",
            asset_type="prop",
            identity_key="story-prop",
            purpose="承载第二节拍的可见变化。",
            source_beat_keys=("beat-2",),
        ),
        VideoAsset(
            asset_key="asset-creature",
            asset_type="creature",
            identity_key="story-creature",
            purpose="承载第三节拍的引导动作。",
            source_beat_keys=("beat-3",),
        ),
    ]
    assets.extend(
        VideoAsset(
            asset_key=f"asset-scene-{beat.position}",
            asset_type="scene",
            identity_key=f"story-scene-{beat.position}",
            purpose=f"呈现第{beat.position}节拍的空间变化。",
            source_beat_keys=(beat.beat_key,),
        )
        for beat in storyboard.beats[3:]
    )
    return AssetInventory(assets=tuple(assets))


def _build_production_plan(inventory: AssetInventory, visual: VisualPlan) -> ProductionPlan:
    prompts = tuple(
        ImagePrompt(
            asset_key=asset.asset_key,
            prompt=f"{asset.purpose} 独立构图, 保持统一视觉语言, 无文字无水印。",
            negative_constraints=visual.negative_constraints,
            aspect_ratio=visual.aspect_ratio,
        )
        for asset in inventory.assets
    )
    return ProductionPlan(kind="image_prompts_only", image_prompts=prompts)
