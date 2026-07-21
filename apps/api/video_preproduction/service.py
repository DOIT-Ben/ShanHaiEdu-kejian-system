"""Stage-gated application service for isolated video preproduction planning."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import ValidationError

from apps.api.video_preproduction.asset_planning import (
    build_asset_inventory,
    build_production_plan,
)
from apps.api.video_preproduction.models import (
    ApprovalFact,
    DurationRecommendation,
    MasterScene,
    PricingSnapshot,
    ReviewableMasterScriptStage,
    ReviewableRoughStoryboardStage,
    ReviewableVideoPreproductionPackage,
    RoughBeat,
    RoughStoryboard,
    StoryComplexity,
    TeacherConfirmation,
    ValidationReport,
    VideoPreproductionRequest,
    VisualPlan,
)
from apps.api.video_preproduction.ports import VideoPreproductionTextGenerator
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
    def __init__(
        self,
        text_generator: VideoPreproductionTextGenerator,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._text_generator = text_generator
        self._clock = clock or (lambda: datetime.now(UTC))

    def generate_master_script(
        self,
        request: VideoPreproductionRequest,
    ) -> ReviewableMasterScriptStage:
        validated = _require_valid_request(request)
        _require_pricing(validated)
        script = self._text_generator.generate_master_script(validated.intro_selection_snapshot)
        if validate_master_script(validated.intro_selection_snapshot, script):
            raise VideoPreproductionError("VIDEO_MASTER_SCRIPT_INVALID")
        return ReviewableMasterScriptStage(
            source_snapshot=validated.intro_selection_snapshot,
            master_script=script,
        )

    def recommend(
        self,
        request: VideoPreproductionRequest,
        master_stage: ReviewableMasterScriptStage,
    ) -> DurationRecommendation:
        validated = _require_valid_request(request)
        _require_master_source(validated, master_stage)
        pricing = _require_pricing(validated)
        complexity = _story_complexity(validated, master_stage)
        preference_seconds = {"economy": -10, "balanced": 0, "quality": 10}[
            validated.cost_preference
        ]
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
            confirmation=confirmed,
        )
        generated_at = self._clock()
        if generated_at < max(confirmed.confirmed_at, approved.approved_at):
            raise VideoPreproductionError("VIDEO_ROUGH_STORYBOARD_INVALID")
        rough = _build_rough_storyboard(
            master_stage,
            confirmed.confirmed_duration_seconds,
            generated_at=generated_at,
        )
        if validate_rough_storyboard(
            master_stage.source_snapshot,
            master_stage.master_script,
            rough,
            expected,
        ):
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
            not_before=max(
                rough_stage.teacher_confirmation.confirmed_at,
                rough_stage.master_script_approval.approved_at,
                rough_stage.rough_storyboard.generated_at,
            ),
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


def _require_valid_request(request: VideoPreproductionRequest) -> VideoPreproductionRequest:
    try:
        return VideoPreproductionRequest.model_validate(request.model_dump(mode="python"))
    except ValidationError as exc:
        pricing_error = any(error["loc"][:1] == ("pricing_snapshot",) for error in exc.errors())
        code = (
            "PRICING_SNAPSHOT_REQUIRED" if pricing_error else "VIDEO_PREPRODUCTION_REQUEST_INVALID"
        )
        raise VideoPreproductionError(code) from exc


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
    confirmation: TeacherConfirmation | None = None,
    not_before: datetime | None = None,
) -> ApprovalFact:
    if approval is None or validate_approval(
        approval,
        kind=kind,
        key=key,
        value=value,
        confirmation=confirmation,
        not_before=not_before,
    ):
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
        confirmation=rough_stage.teacher_confirmation,
    )
    if validate_rough_storyboard(
        master_stage.source_snapshot,
        master_stage.master_script,
        rough_stage.rough_storyboard,
        expected,
    ):
        raise VideoPreproductionError("VIDEO_ROUGH_STORYBOARD_INVALID")


def _build_rough_storyboard(
    master_stage: ReviewableMasterScriptStage,
    target_duration: int,
    *,
    generated_at: datetime,
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
        generated_at=generated_at,
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
    asset_keys = tuple(requirement.asset_key for requirement in scene.asset_requirements)
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
    inventory = build_asset_inventory(
        master_stage.master_script.scenes,
        rough_stage.rough_storyboard,
    )
    plan = build_production_plan(inventory, visual)
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
