from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast, get_type_hints

import pytest
from pydantic import BaseModel

from apps.api.video_preproduction.fake import ScriptedDeterministicTextFake
from apps.api.video_preproduction.models import (
    ApprovalFact,
    ApprovalKind,
    DurationRecommendation,
    IntroSelectionSnapshot,
    MasterScript,
    PricingSnapshot,
    TeacherConfirmation,
    VideoPreproductionRequest,
)
from apps.api.video_preproduction.ports import VideoPreproductionTextGenerator
from apps.api.video_preproduction.service import (
    VideoPreproductionError,
    VideoPreproductionService,
)
from apps.api.video_preproduction.validator import (
    canonical_fact_hash,
    canonical_package_bytes,
    canonical_package_hash,
    inventory_assets,
    validate_package,
)

NOW = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)


def request(
    *,
    pricing: PricingSnapshot | None = None,
    creative_concept: str = "机器人逐个核对补给盒与卡槽的一一对应。",
    course_anchor: str = "五个卡槽已占用但没有数字标签。",
) -> VideoPreproductionRequest:
    return VideoPreproductionRequest(
        intro_selection_snapshot=IntroSelectionSnapshot(
            snapshot_id="intro-selection-001",
            version="1",
            option_key="INTRO-APP-01",
            title="机器人补给舱装载",
            creative_concept=creative_concept,
            hook="舱门即将关闭, 扫描灯提示一个卡槽状态不明。",
            course_anchor=course_anchor,
            classroom_first_question="舱里有几个补给盒? 怎样检查才不会重复或遗漏?",
            handoff_moment="所有补给盒与卡槽一一对齐、机器人准备重新扫描时停止。",
            must_not_preteach=("比较大小", "第几", "分与合"),
        ),
        pricing_snapshot=pricing
        or PricingSnapshot(
            version="video-pricing-2026-07",
            currency="CNY",
            image_candidate_unit_price=Decimal("0.80"),
            candidates_per_asset=2,
        ),
        aspect_ratio="16:9",
        language="zh-CN",
        cost_preference="balanced",
    )


def confirmation(recommendation: DurationRecommendation) -> TeacherConfirmation:
    return TeacherConfirmation(
        pricing_version=recommendation.pricing_version,
        currency=recommendation.currency,
        confirmed_duration_seconds=recommendation.recommended_duration_seconds,
        confirmed_estimated_cost=recommendation.estimated_cost,
        confirmed_at=NOW,
    )


def approval(
    subject_kind: ApprovalKind,
    subject_key: str,
    value: BaseModel,
    *,
    confirmation_fact: TeacherConfirmation | None = None,
) -> ApprovalFact:
    return ApprovalFact(
        subject_kind=subject_kind,
        subject_key=subject_key,
        subject_hash=canonical_fact_hash(value),
        confirmation_hash=(
            canonical_fact_hash(confirmation_fact) if confirmation_fact is not None else None
        ),
        approved_by="teacher-001",
        approved_at=NOW,
    )


def build_package(*, payload: VideoPreproductionRequest | None = None):
    selected = payload or request()
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake)
    master_stage = service.generate_master_script(selected)
    recommendation = service.recommend(selected, master_stage)
    confirmed = confirmation(recommendation)
    master_approval = approval(
        "master_script",
        master_stage.master_script.master_script_key,
        master_stage.master_script,
        confirmation_fact=confirmed,
    )
    rough_stage = service.generate_rough_storyboard(
        selected,
        master_stage,
        recommendation,
        confirmed,
        master_approval,
    )
    rough_approval = approval(
        "rough_storyboard",
        rough_stage.rough_storyboard.rough_storyboard_key,
        rough_stage.rough_storyboard,
    )
    package = service.generate_package(selected, rough_stage, rough_approval)
    return package, fake, service, selected, master_stage, recommendation, rough_stage


def test_master_precedes_story_based_recommendation_and_teacher_confirmation() -> None:
    payload = request()
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake)
    master_stage = service.generate_master_script(payload)
    recommendation = service.recommend(payload, master_stage)
    assert fake.calls == 1
    assert recommendation.story_complexity.scene_count == len(master_stage.master_script.scenes)
    assert recommendation.story_complexity.visible_beat_count == sum(
        len(scene.visible_beats) for scene in master_stage.master_script.scenes
    )
    assert recommendation.story_complexity.estimated_shot_count == sum(
        scene.estimated_shot_count for scene in master_stage.master_script.scenes
    )
    assert recommendation.story_complexity.handoff_complexity > 0
    assert 60 <= recommendation.recommended_duration_seconds <= 180


def test_master_generation_accepts_a_provider_neutral_text_generator() -> None:
    class DelegatingTextGenerator:
        def __init__(self) -> None:
            self.calls = 0
            self._fake = ScriptedDeterministicTextFake()

        def generate_master_script(self, snapshot: IntroSelectionSnapshot) -> MasterScript:
            self.calls += 1
            return self._fake.generate_master_script(snapshot)

    generator = DelegatingTextGenerator()
    service = VideoPreproductionService(generator)

    stage = service.generate_master_script(request())

    assert generator.calls == 1
    assert stage.master_script.selected_intro_snapshot_id == stage.source_snapshot.snapshot_id
    hints = get_type_hints(VideoPreproductionService.__init__)
    assert hints["text_generator"] is VideoPreproductionTextGenerator


def test_master_generation_rejects_missing_or_invalid_pricing_before_fake_call() -> None:
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake)
    valid = request()
    assert valid.pricing_snapshot is not None
    invalid_pricing = valid.pricing_snapshot.model_copy(
        update={
            "version": "",
            "currency": "usd",
            "image_candidate_unit_price": Decimal("0"),
        }
    )
    for payload in (
        valid.model_copy(update={"pricing_snapshot": None}),
        valid.model_copy(update={"pricing_snapshot": invalid_pricing}),
        *(
            valid.model_copy(
                update={
                    "pricing_snapshot": PricingSnapshot.model_construct(
                        version="video-pricing-constructed",
                        currency="CNY",
                        image_candidate_unit_price=Decimal("0.80"),
                        candidates_per_asset=count,
                    )
                }
            )
            for count in (0, 9)
        ),
    ):
        with pytest.raises(VideoPreproductionError) as caught:
            service.generate_master_script(payload)
        assert caught.value.code == "PRICING_SNAPSHOT_REQUIRED"
    snapshot = valid.intro_selection_snapshot
    snapshot_data = snapshot.model_dump(mode="python")
    snapshot_data["must_not_preteach"] = ()
    invalid_snapshot = cast(Any, IntroSelectionSnapshot.model_construct)(**snapshot_data)
    invalid_request = VideoPreproductionRequest.model_construct(
        intro_selection_snapshot=invalid_snapshot,
        pricing_snapshot=valid.pricing_snapshot,
        aspect_ratio=valid.aspect_ratio,
        language=valid.language,
        cost_preference=valid.cost_preference,
    )
    with pytest.raises(VideoPreproductionError) as caught:
        service.generate_master_script(invalid_request)
    assert caught.value.code == "VIDEO_PREPRODUCTION_REQUEST_INVALID"
    assert fake.calls == 0


def test_rough_storyboard_requires_confirmation_and_master_approval() -> None:
    payload = request()
    service = VideoPreproductionService(ScriptedDeterministicTextFake())
    master_stage = service.generate_master_script(payload)
    recommendation = service.recommend(payload, master_stage)
    confirmed = confirmation(recommendation)
    master_approval = approval(
        "master_script",
        master_stage.master_script.master_script_key,
        master_stage.master_script,
        confirmation_fact=confirmed,
    )
    with pytest.raises(VideoPreproductionError) as missing_confirmation:
        service.generate_rough_storyboard(
            payload, master_stage, recommendation, None, master_approval
        )
    assert missing_confirmation.value.code == "TEACHER_CONFIRMATION_REQUIRED"
    with pytest.raises(VideoPreproductionError) as missing_approval:
        service.generate_rough_storyboard(
            payload,
            master_stage,
            recommendation,
            confirmed,
            None,
        )
    assert missing_approval.value.code == "MASTER_SCRIPT_APPROVAL_REQUIRED"
    invalid_approval = master_approval.model_copy(
        update={
            "confirmation_hash": "0" * 64,
            "approved_at": confirmed.confirmed_at - timedelta(seconds=1),
        }
    )
    with pytest.raises(VideoPreproductionError) as caught:
        service.generate_rough_storyboard(
            payload,
            master_stage,
            recommendation,
            confirmed,
            invalid_approval,
        )
    assert caught.value.code == "MASTER_SCRIPT_APPROVAL_REQUIRED"


def test_final_package_revalidates_recommendation_and_confirmation_facts() -> None:
    package, _, service, payload, _, _, rough_stage = build_package()
    rough_approval = approval(
        "rough_storyboard",
        rough_stage.rough_storyboard.rough_storyboard_key,
        rough_stage.rough_storyboard,
    )
    confirmation_changes = (
        {"pricing_version": "tampered"},
        {"currency": "USD"},
        {"confirmed_duration_seconds": 180},
        {"confirmed_estimated_cost": Decimal("999.00")},
    )
    for change in confirmation_changes:
        tampered_stage = rough_stage.model_copy(
            update={
                "teacher_confirmation": rough_stage.teacher_confirmation.model_copy(update=change)
            }
        )
        with pytest.raises(VideoPreproductionError) as caught:
            service.generate_package(payload, tampered_stage, rough_approval)
        assert caught.value.code == "TEACHER_CONFIRMATION_REQUIRED"
    recommendation_changes = (
        {"pricing_version": "tampered"},
        {"currency": "USD"},
        {"recommended_duration_seconds": 180},
        {"estimated_cost": Decimal("999.00")},
    )
    for change in recommendation_changes:
        tampered_stage = rough_stage.model_copy(
            update={
                "duration_recommendation": rough_stage.duration_recommendation.model_copy(
                    update=change
                )
            }
        )
        with pytest.raises(VideoPreproductionError) as caught:
            service.generate_package(payload, tampered_stage, rough_approval)
        assert caught.value.code == "DURATION_RECOMMENDATION_STALE"
    assert package.validation_report.valid is True


def test_story_structure_and_server_price_facts_change_recommendations() -> None:
    service = VideoPreproductionService(ScriptedDeterministicTextFake())
    baseline_request = request()
    baseline_master = service.generate_master_script(baseline_request)
    baseline = service.recommend(baseline_request, baseline_master)
    complex_request = request(
        creative_concept="多场景连续动作与可见变化。" * 20,
        course_anchor="课程锚点需要在多次状态转换后出现。" * 12,
    )
    complex_master = service.generate_master_script(complex_request)
    complex_story = service.recommend(complex_request, complex_master)
    expensive_request = request(
        pricing=PricingSnapshot(
            version="video-pricing-2026-08",
            currency="CNY",
            image_candidate_unit_price=Decimal("2.00"),
            candidates_per_asset=2,
        )
    )
    expensive_master = service.generate_master_script(expensive_request)
    expensive = service.recommend(expensive_request, expensive_master)
    assert complex_story.story_complexity.scene_count > baseline.story_complexity.scene_count
    assert complex_story.story_complexity.visible_beat_count > (
        baseline.story_complexity.visible_beat_count
    )
    assert complex_story.recommended_duration_seconds > baseline.recommended_duration_seconds
    assert complex_story.estimated_cost > baseline.estimated_cost
    assert expensive.pricing_version == "video-pricing-2026-08"
    assert expensive.recommended_duration_seconds < baseline.recommended_duration_seconds
    assert expensive.estimated_cost > baseline.estimated_cost


def test_scene_and_beat_mapping_is_complete_and_ends_at_handoff() -> None:
    package, *_ = build_package()
    expected_events = [
        (scene.scene_key, position, event)
        for scene in package.master_script.scenes
        for position, event in enumerate(scene.visible_beats, start=1)
    ]
    actual_events = [
        (beat.scene_key, beat.scene_beat_position, beat.main_event)
        for beat in package.rough_storyboard.beats
    ]
    assert actual_events == expected_events
    assert package.rough_storyboard.beats[-1].end_state == (package.source_snapshot.handoff_moment)


def test_classified_asset_inventory_and_bidirectional_links_are_exact() -> None:
    package, *_ = build_package()
    inventory = package.asset_inventory
    beat_links = {
        (beat.beat_key, asset_key)
        for beat in package.rough_storyboard.beats
        for asset_key in beat.asset_keys
    }
    source_links = {
        (beat_key, asset.asset_key)
        for asset in inventory_assets(inventory)
        for beat_key in asset.source_beat_keys
    }
    assert inventory.characters
    assert inventory.scenes
    assert inventory.props
    assert inventory.creatures == ()
    assert beat_links == source_links
    assert {prompt.asset_key for prompt in package.production_plan.image_prompts} == {
        asset.asset_key for asset in inventory_assets(inventory)
    }


def test_validator_rejects_mapping_link_and_prompt_drift() -> None:
    package, *_ = build_package()
    last_beat = package.rough_storyboard.beats[-1].model_copy(
        update={"end_state": "not-handoff", "asset_keys": ("missing-asset",)}
    )
    broken_rough = package.rough_storyboard.model_copy(
        update={
            "beats": (*package.rough_storyboard.beats[:-1], last_beat),
            "total_duration_seconds": package.rough_storyboard.total_duration_seconds + 1,
        }
    )
    first_prompt = package.production_plan.image_prompts[0]
    broken_prompt = first_prompt.model_copy(
        update={"aspect_ratio": "9:16", "negative_constraints": ()}
    )
    broken_plan = package.production_plan.model_copy(
        update={
            "image_prompts": (
                broken_prompt,
                broken_prompt,
                *package.production_plan.image_prompts[2:],
            )
        }
    )
    report = validate_package(
        package.model_copy(
            update={"rough_storyboard": broken_rough, "production_plan": broken_plan}
        )
    )
    assert report.valid is False
    assert "rough storyboard must end at the selected handoff moment" in report.errors
    assert "rough beat references an unknown asset" in report.errors
    assert "asset source and beat asset references must match exactly" in report.errors
    assert "image prompt asset keys must be unique" in report.errors
    assert "image prompts must use the visual plan aspect ratio" in report.errors
    assert "image prompts must retain visual plan negative constraints" in report.errors
    assert "rough storyboard declared duration must equal beat durations" in report.errors


def test_canonical_serialization_bytes_are_stable_and_detect_tampering() -> None:
    package, *_ = build_package()
    round_tripped = package.model_validate_json(package.model_dump_json(indent=2))
    assert canonical_package_bytes(round_tripped) == canonical_package_bytes(package)
    assert canonical_package_hash(round_tripped) == package.canonical_hash

    tampered = package.model_copy(
        update={"master_script": package.master_script.model_copy(update={"title": "tampered"})}
    )
    report = validate_package(tampered)
    assert report.valid is False
    assert "canonical hash does not match package content" in report.errors
