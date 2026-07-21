"""Internal immutable facts for the #142 video preproduction slice."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

ApprovalKind = Literal["master_script", "rough_storyboard"]
AssetType = Literal["character", "scene", "prop", "creature"]
AspectRatio = Literal["16:9", "9:16"]
NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000),
]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
VersionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
TitleText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
MediumText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000),
]
Currency = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[A-Z]{3}$"),
]


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntroSelectionSnapshot(_FrozenModel):
    snapshot_id: ShortText
    version: VersionText
    option_key: ShortText
    title: TitleText
    creative_concept: NonEmptyText
    hook: MediumText
    course_anchor: MediumText
    classroom_first_question: MediumText
    handoff_moment: MediumText
    must_not_preteach: tuple[NonEmptyText, ...] = Field(min_length=1, max_length=50)


class PricingSnapshot(_FrozenModel):
    version: ShortText
    currency: Currency
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
    pricing_version: ShortText
    currency: Currency
    story_complexity: StoryComplexity
    rationale: tuple[NonEmptyText, ...]


class TeacherConfirmation(_FrozenModel):
    pricing_version: ShortText
    currency: Currency
    confirmed_duration_seconds: int = Field(ge=60, le=180)
    confirmed_estimated_cost: Decimal = Field(ge=0)
    confirmed_at: AwareDatetime


class ApprovalFact(_FrozenModel):
    subject_kind: ApprovalKind
    subject_key: ShortText
    subject_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    approved_by: ShortText
    approved_at: AwareDatetime


class SceneAssetRequirement(_FrozenModel):
    asset_key: ShortText
    asset_type: AssetType
    identity_key: ShortText
    purpose: MediumText
    visual_description: NonEmptyText


class MasterScene(_FrozenModel):
    scene_key: ShortText
    position: int = Field(ge=1)
    purpose: NonEmptyText
    location: NonEmptyText
    action: NonEmptyText
    visible_change: NonEmptyText
    visible_beats: tuple[NonEmptyText, ...] = Field(min_length=1, max_length=4)
    estimated_shot_count: int = Field(ge=1, le=6)
    narration: NonEmptyText
    dialogue: NonEmptyText
    sound_intent: NonEmptyText
    start_state: NonEmptyText
    end_state: NonEmptyText
    asset_requirements: tuple[SceneAssetRequirement, ...] = Field(min_length=1)


class MasterScript(_FrozenModel):
    master_script_key: ShortText
    selected_intro_snapshot_id: ShortText
    selected_intro_snapshot_version: VersionText
    selected_intro_option_key: ShortText
    title: TitleText
    creative_concept: NonEmptyText
    course_anchor: MediumText
    narrative_purpose: NonEmptyText
    complete_story: NonEmptyText
    scenes: tuple[MasterScene, ...] = Field(min_length=1)
    ends_at_handoff: bool


class ReviewableMasterScriptStage(_FrozenModel):
    source_snapshot: IntroSelectionSnapshot
    master_script: MasterScript


class RoughBeat(_FrozenModel):
    beat_key: ShortText
    scene_key: ShortText
    scene_beat_position: int = Field(ge=1, le=4)
    position: int = Field(ge=1)
    main_event: NonEmptyText
    start_state: NonEmptyText
    end_state: NonEmptyText
    duration_seconds: int = Field(gt=0)
    asset_keys: tuple[ShortText, ...] = Field(min_length=1)


class RoughStoryboard(_FrozenModel):
    rough_storyboard_key: ShortText
    source_master_script_key: ShortText
    beats: tuple[RoughBeat, ...] = Field(min_length=1)
    total_duration_seconds: int = Field(ge=60, le=180)
    generated_at: AwareDatetime


class ReviewableRoughStoryboardStage(_FrozenModel):
    master_stage: ReviewableMasterScriptStage
    duration_recommendation: DurationRecommendation
    teacher_confirmation: TeacherConfirmation
    master_script_approval: ApprovalFact
    rough_storyboard: RoughStoryboard


class VideoAsset(_FrozenModel):
    asset_key: ShortText
    asset_type: AssetType
    identity_key: ShortText
    purpose: NonEmptyText
    visual_description: NonEmptyText
    source_beat_keys: tuple[ShortText, ...] = Field(min_length=1)


class AssetInventory(_FrozenModel):
    characters: tuple[VideoAsset, ...] = Field(min_length=1)
    scenes: tuple[VideoAsset, ...] = Field(min_length=1)
    props: tuple[VideoAsset, ...] = Field(min_length=1)
    creatures: tuple[VideoAsset, ...] = ()


class VisualPlan(_FrozenModel):
    aspect_ratio: AspectRatio
    language: Literal["zh-CN"]
    consistency_principles: tuple[NonEmptyText, ...] = Field(min_length=1)
    negative_constraints: tuple[ShortText, ...] = Field(min_length=1)


class ImagePrompt(_FrozenModel):
    asset_key: ShortText
    prompt: NonEmptyText
    negative_constraints: tuple[ShortText, ...] = Field(min_length=1)
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
