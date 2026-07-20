"""Stage-gated application service for isolated video preproduction planning."""

from __future__ import annotations

from decimal import Decimal

from pydantic import ValidationError

from apps.api.video_preproduction.fake import ScriptedDeterministicTextFake
from apps.api.video_preproduction.models import (
    ApprovalFact,
    AssetInventory,
    DurationRecommendation,
    ImagePrompt,
    MasterScene,
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
    inventory_assets,
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

    def generate_master_script(
        self,
        request: VideoPreproductionRequest,
    ) -> ReviewableMasterScriptStage:
        _require_pricing(request)
        script = self._text_fake.generate_master_script(request.intro_selection_snapshot)
        if validate_master_script(request.intro_selection_snapshot, script):
            raise VideoPreproductionError("VIDEO_MASTER_SCRIPT_INVALID")
        return ReviewableMasterScriptStage(
            source_snapshot=request.intro_selection_snapshot,
            master_script=script,
        )

    def recommend(
        self,
        request: VideoPreproductionRequest,
        master_stage: ReviewableMasterScriptStage,
    ) -> DurationRecommendation:
        _require_master_source(request, master_stage)
        pricing = _require_pricing(request)
        complexity = _story_complexity(request, master_stage)
        preference_seconds = {"economy": -10, "balanced": 0, "quality": 10}[request.cost_preference]
        price_seconds = -10 if pricing.image_candidate_unit_price > Decimal("1.00") else 0
        raw_duration = (
            complexity.scene_count * 12
            + complexity.visible_beat_count * 8
            + complexity.estimated_shot_count * 3
            + complexity.handoff_complexity * 5
            + preference_seconds
            + price_seconds
        )
        cost = (
            pricing.image_candidate_unit_price
            * pricing.candidates_per_asset
            * complexity.estimated_asset_count
        )
        return DurationRecommendation(
            recommended_duration_seconds=min(180, max(60, raw_duration)),
            estimated_cost=cost,
            pricing_version=pricing.version,
            currency=pricing.currency,
            story_complexity=complexity,
            rationale=(
                f"master scenes: {complexity.scene_count}",
                f"visible beats: {complexity.visible_beat_count}",
                f"estimated shots: {complexity.estimated_shot_count}",
                f"handoff complexity: {complexity.handoff_complexity}",
                f"pricing snapshot: {pricing.version}",
            ),
        )

    def generate_rough_storyboard(
        self,
        request: VideoPreproductionRequest,
        master_stage: ReviewableMasterScriptStage,
        recommendation: DurationRecommendation,
        confirmation: TeacherConfirmation | None,
        master_approval: ApprovalFact | None,
    ) -> ReviewableRoughStoryboardStage:
        expected = self.recommend(request, master_stage)
        if recommendation != expected:
            raise VideoPreproductionError("DURATION_RECOMMENDATION_STALE")
        confirmed = _require_confirmation(confirmation, expected)
        approved = _require_approval(
            master_approval,
            kind="master_script",
            key=master_stage.master_script.master_script_key,
            value=master_stage.master_script,
            error_code="MASTER_SCRIPT_APPROVAL_REQUIRED",
        )
        rough = _build_rough_storyboard(master_stage, confirmed.confirmed_duration_seconds)
        if validate_rough_storyboard(master_stage.master_script, rough, expected):
            raise VideoPreproductionError("VIDEO_ROUGH_STORYBOARD_INVALID")
        return ReviewableRoughStoryboardStage(
            master_stage=master_stage,
            duration_recommendation=expected,
            teacher_confirmation=confirmed,
            master_script_approval=approved,
            rough_storyboard=rough,
        )

    def generate_package(
        self,
        request: VideoPreproductionRequest,
        rough_stage: ReviewableRoughStoryboardStage,
        rough_approval: ApprovalFact | None,
    ) -> ReviewableVideoPreproductionPackage:
        _revalidate_stage(self, request, rough_stage)
        approved = _require_approval(
            rough_approval,
            kind="rough_storyboard",
            key=rough_stage.rough_storyboard.rough_storyboard_key,
            value=rough_stage.rough_storyboard,
            error_code="ROUGH_STORYBOARD_APPROVAL_REQUIRED",
        )
        package = _build_package(request, rough_stage, approved)
        report = validate_package(package)
        if not report.valid:
            raise VideoPreproductionError("VIDEO_PREPRODUCTION_INVALID")
        return package.model_copy(update={"validation_report": report})


def _require_master_source(
    request: VideoPreproductionRequest,
    master_stage: ReviewableMasterScriptStage,
) -> None:
    if master_stage.source_snapshot != request.intro_selection_snapshot:
        raise VideoPreproductionError("VIDEO_PREPRODUCTION_SOURCE_STALE")
    if validate_master_script(master_stage.source_snapshot, master_stage.master_script):
        raise VideoPreproductionError("VIDEO_MASTER_SCRIPT_INVALID")


def _require_pricing(request: VideoPreproductionRequest) -> PricingSnapshot:
    pricing = request.pricing_snapshot
    if pricing is None:
        raise VideoPreproductionError("PRICING_SNAPSHOT_REQUIRED")
    try:
        return PricingSnapshot.model_validate(pricing.model_dump(mode="python"))
    except ValidationError as exc:
        raise VideoPreproductionError("PRICING_SNAPSHOT_REQUIRED") from exc


def _story_complexity(
    request: VideoPreproductionRequest,
    master_stage: ReviewableMasterScriptStage,
) -> StoryComplexity:
    scenes = master_stage.master_script.scenes
    visible_beats = sum(len(scene.visible_beats) for scene in scenes)
    estimated_shots = sum(scene.estimated_shot_count for scene in scenes)
    handoff_chars = len(master_stage.master_script.scenes[-1].end_state.strip())
    handoff_complexity = min(3, max(1, (handoff_chars + 39) // 40))
    return StoryComplexity(
        scene_count=len(scenes),
        visible_beat_count=visible_beats,
        estimated_shot_count=estimated_shots,
        handoff_complexity=handoff_complexity,
        estimated_asset_count=len(scenes) + 2,
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


def _revalidate_stage(
    service: VideoPreproductionService,
    request: VideoPreproductionRequest,
    rough_stage: ReviewableRoughStoryboardStage,
) -> None:
    master_stage = rough_stage.master_stage
    expected = service.recommend(request, master_stage)
    if rough_stage.duration_recommendation != expected:
        raise VideoPreproductionError("DURATION_RECOMMENDATION_STALE")
    _require_confirmation(rough_stage.teacher_confirmation, expected)
    _require_approval(
        rough_stage.master_script_approval,
        kind="master_script",
        key=master_stage.master_script.master_script_key,
        value=master_stage.master_script,
        error_code="MASTER_SCRIPT_APPROVAL_REQUIRED",
    )
    if validate_rough_storyboard(
        master_stage.master_script, rough_stage.rough_storyboard, expected
    ):
        raise VideoPreproductionError("VIDEO_ROUGH_STORYBOARD_INVALID")


def _build_rough_storyboard(
    master_stage: ReviewableMasterScriptStage,
    target_duration: int,
) -> RoughStoryboard:
    master = master_stage.master_script
    event_count = sum(len(scene.visible_beats) for scene in master.scenes)
    durations = _split_duration(target_duration, event_count)
    beats: list[RoughBeat] = []
    for scene in master.scenes:
        for event_position, event in enumerate(scene.visible_beats, start=1):
            beats.append(_build_beat(scene, event, event_position, len(beats) + 1, durations))
    return RoughStoryboard(
        rough_storyboard_key=f"rough-{master.master_script_key}",
        source_master_script_key=master.master_script_key,
        beats=tuple(beats),
        total_duration_seconds=sum(beat.duration_seconds for beat in beats),
    )


def _build_beat(
    scene: MasterScene,
    event: str,
    event_position: int,
    position: int,
    durations: tuple[int, ...],
) -> RoughBeat:
    event_count = len(scene.visible_beats)
    start_state = (
        scene.start_state if event_position == 1 else f"{scene.scene_key}-beat-{event_position - 1}"
    )
    end_state = (
        scene.end_state
        if event_position == event_count
        else f"{scene.scene_key}-beat-{event_position}"
    )
    asset_keys = ("asset-character", f"asset-scene-{scene.position}")
    if position == 1:
        asset_keys = (*asset_keys, "asset-prop")
    return RoughBeat(
        beat_key=f"beat-{position}",
        scene_key=scene.scene_key,
        scene_beat_position=event_position,
        position=position,
        main_event=event,
        start_state=start_state,
        end_state=end_state,
        duration_seconds=durations[position - 1],
        asset_keys=asset_keys,
    )


def _split_duration(total_seconds: int, count: int) -> tuple[int, ...]:
    quotient, remainder = divmod(total_seconds, count)
    return tuple(quotient + (1 if position < remainder else 0) for position in range(count))


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
        teacher_confirmation=rough_stage.teacher_confirmation,
        duration_recommendation=rough_stage.duration_recommendation,
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
            "主体、场景和道具保持同一造型比例与材质。",
            "每个资产独立构图, 使用清楚的承托面与接触阴影。",
        ),
        negative_constraints=("文字", "水印", "Logo", "额外主体"),
    )


def _build_asset_inventory(storyboard: RoughStoryboard) -> AssetInventory:
    all_beat_keys = tuple(beat.beat_key for beat in storyboard.beats)
    character = VideoAsset(
        asset_key="asset-character",
        asset_type="character",
        identity_key="story-character",
        purpose="承载故事主要行动。",
        source_beat_keys=all_beat_keys,
    )
    scene_keys = tuple(dict.fromkeys(beat.scene_key for beat in storyboard.beats))
    scenes = tuple(
        VideoAsset(
            asset_key=f"asset-scene-{scene_position}",
            asset_type="scene",
            identity_key=f"story-scene-{scene_position}",
            purpose=f"呈现第{scene_position}场空间。",
            source_beat_keys=tuple(
                beat.beat_key for beat in storyboard.beats if beat.scene_key == scene_key
            ),
        )
        for scene_position, scene_key in enumerate(scene_keys, start=1)
    )
    prop = VideoAsset(
        asset_key="asset-prop",
        asset_type="prop",
        identity_key="story-prop",
        purpose="承载开场可见变化。",
        source_beat_keys=(storyboard.beats[0].beat_key,),
    )
    return AssetInventory(characters=(character,), scenes=scenes, props=(prop,), creatures=())


def _build_production_plan(inventory: AssetInventory, visual: VisualPlan) -> ProductionPlan:
    prompts = tuple(
        ImagePrompt(
            asset_key=asset.asset_key,
            prompt=f"{asset.purpose} 独立构图, 保持统一视觉语言, 无文字无水印。",
            negative_constraints=visual.negative_constraints,
            aspect_ratio=visual.aspect_ratio,
        )
        for asset in inventory_assets(inventory)
    )
    return ProductionPlan(kind="image_prompts_only", image_prompts=prompts)
