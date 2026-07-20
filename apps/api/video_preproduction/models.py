"""Internal immutable facts for the #142 video preproduction slice."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ApprovalKind = Literal["master_script", "rough_storyboard"]
AssetType = Literal["character", "scene", "prop", "creature"]
AspectRatio = Literal["16:9", "9:16"]


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntroSelectionSnapshot(_FrozenModel):
    snapshot_id: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=80)
    option_key: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    creative_concept: str = Field(min_length=1, max_length=10_000)
    hook: str = Field(min_length=1, max_length=5_000)
    course_anchor: str = Field(min_length=1, max_length=5_000)
    classroom_first_question: str = Field(min_length=1, max_length=5_000)
    handoff_moment: str = Field(min_length=1, max_length=5_000)
    must_not_preteach: tuple[str, ...] = Field(min_length=1, max_length=50)


class PricingSnapshot(_FrozenModel):
    version: str = Field(min_length=1, max_length=160)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    image_candidate_unit_price: Decimal = Field(gt=0)
    candidates_per_asset: int = Field(ge=1, le=8)


class VideoPreproductionRequest(_FrozenModel):
    intro_selection_snapshot: IntroSelectionSnapshot
    pricing_snapshot: PricingSnapshot | None
    aspect_ratio: AspectRatio
    language: Literal["zh-CN"]
    cost_preference: Literal["economy", "balanced", "quality"]


class StoryComplexity(_FrozenModel):
    scene_count: int = Field(ge=3, le=6)
    visible_beat_count: int = Field(ge=3, le=24)
    estimated_shot_count: int = Field(ge=3, le=30)
    handoff_complexity: int = Field(ge=1, le=3)
    estimated_asset_count: int = Field(ge=5, le=8)


class DurationRecommendation(_FrozenModel):
    recommended_duration_seconds: int = Field(ge=60, le=180)
    estimated_cost: Decimal = Field(ge=0)
    pricing_version: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    story_complexity: StoryComplexity
    rationale: tuple[str, ...]


class TeacherConfirmation(_FrozenModel):
    pricing_version: str = Field(min_length=1, max_length=160)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    confirmed_duration_seconds: int = Field(ge=60, le=180)
    confirmed_estimated_cost: Decimal = Field(ge=0)
    confirmed_at: datetime


class ApprovalFact(_FrozenModel):
    subject_kind: ApprovalKind
    subject_key: str = Field(min_length=1, max_length=160)
    subject_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    approved_by: str = Field(min_length=1, max_length=160)
    approved_at: datetime


class MasterScene(_FrozenModel):
    scene_key: str
    position: int = Field(ge=1)
    purpose: str
    visible_change: str
    visible_beats: tuple[str, ...] = Field(min_length=1, max_length=4)
    estimated_shot_count: int = Field(ge=1, le=6)
    narration: str
    start_state: str
    end_state: str


class MasterScript(_FrozenModel):
    master_script_key: str
    selected_intro_snapshot_id: str
    selected_intro_snapshot_version: str
    selected_intro_option_key: str
    title: str
    creative_concept: str
    course_anchor: str
    narrative_purpose: str
    complete_story: str
    scenes: tuple[MasterScene, ...] = Field(min_length=1)
    ends_at_handoff: bool


class ReviewableMasterScriptStage(_FrozenModel):
    source_snapshot: IntroSelectionSnapshot
    master_script: MasterScript


class RoughBeat(_FrozenModel):
    beat_key: str
    scene_key: str
    scene_beat_position: int = Field(ge=1, le=4)
    position: int = Field(ge=1)
    main_event: str
    start_state: str
    end_state: str
    duration_seconds: int = Field(gt=0)
    asset_keys: tuple[str, ...] = Field(min_length=1)


class RoughStoryboard(_FrozenModel):
    rough_storyboard_key: str
    source_master_script_key: str
    beats: tuple[RoughBeat, ...] = Field(min_length=1)
    total_duration_seconds: int = Field(ge=60, le=180)


class ReviewableRoughStoryboardStage(_FrozenModel):
    master_stage: ReviewableMasterScriptStage
    duration_recommendation: DurationRecommendation
    teacher_confirmation: TeacherConfirmation
    master_script_approval: ApprovalFact
    rough_storyboard: RoughStoryboard


class VideoAsset(_FrozenModel):
    asset_key: str
    asset_type: AssetType
    identity_key: str
    purpose: str
    source_beat_keys: tuple[str, ...] = Field(min_length=1)


class AssetInventory(_FrozenModel):
    characters: tuple[VideoAsset, ...] = Field(min_length=1)
    scenes: tuple[VideoAsset, ...] = Field(min_length=1)
    props: tuple[VideoAsset, ...] = Field(min_length=1)
    creatures: tuple[VideoAsset, ...] = ()


class VisualPlan(_FrozenModel):
    aspect_ratio: AspectRatio
    language: Literal["zh-CN"]
    consistency_principles: tuple[str, ...] = Field(min_length=1)
    negative_constraints: tuple[str, ...] = Field(min_length=1)


class ImagePrompt(_FrozenModel):
    asset_key: str
    prompt: str
    negative_constraints: tuple[str, ...] = Field(min_length=1)
    aspect_ratio: AspectRatio


class ProductionPlan(_FrozenModel):
    kind: Literal["image_prompts_only"]
    image_prompts: tuple[ImagePrompt, ...] = Field(min_length=4)
    media_operations: tuple[()] = ()


class ValidationReport(_FrozenModel):
    valid: bool
    errors: tuple[str, ...]


class ReviewableVideoPreproductionPackage(_FrozenModel):
    source_snapshot: IntroSelectionSnapshot
    teacher_confirmation: TeacherConfirmation
    duration_recommendation: DurationRecommendation
    master_script: MasterScript
    master_script_approval: ApprovalFact
    rough_storyboard: RoughStoryboard
    rough_storyboard_approval: ApprovalFact
    visual_plan: VisualPlan
    asset_inventory: AssetInventory
    production_plan: ProductionPlan
    validation_report: ValidationReport
    canonical_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
