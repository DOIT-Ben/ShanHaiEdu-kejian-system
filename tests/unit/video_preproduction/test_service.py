from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel

from apps.api.video_preproduction.fake import ScriptedDeterministicTextFake
from apps.api.video_preproduction.models import (
    ApprovalFact,
    ApprovalKind,
    DurationRecommendation,
    IntroSelectionSnapshot,
    PricingSnapshot,
    TeacherConfirmation,
    VideoPreproductionRequest,
)
from apps.api.video_preproduction.service import (
    VideoPreproductionError,
    VideoPreproductionService,
)
from apps.api.video_preproduction.validator import (
    canonical_fact_hash,
    canonical_package_hash,
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


def approval(subject_kind: ApprovalKind, subject_key: str, value: BaseModel) -> ApprovalFact:
    return ApprovalFact(
        subject_kind=subject_kind,
        subject_key=subject_key,
        subject_hash=canonical_fact_hash(value),
        approved_by="teacher-001",
        approved_at=NOW,
    )


def build_package():
    payload = request()
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake)
    recommendation = service.recommend(payload)

    with pytest.raises(VideoPreproductionError) as missing_confirmation:
        service.generate_master_script(payload, recommendation, None)

    assert missing_confirmation.value.code == "TEACHER_CONFIRMATION_REQUIRED"
    assert fake.calls == 0
    master_stage = service.generate_master_script(
        payload,
        recommendation,
        confirmation(recommendation),
    )
    master_approval = approval(
        "master_script",
        master_stage.master_script.master_script_key,
        master_stage.master_script,
    )
    rough_stage = service.generate_rough_storyboard(master_stage, master_approval)
    rough_approval = approval(
        "rough_storyboard",
        rough_stage.rough_storyboard.rough_storyboard_key,
        rough_stage.rough_storyboard,
    )
    package = service.generate_package(payload, rough_stage, rough_approval)
    return package, fake, service, payload, master_stage, rough_stage


def test_recommendation_stops_before_teacher_confirmation_and_master_generation() -> None:
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake)

    recommendation = service.recommend(request())

    assert 60 <= recommendation.recommended_duration_seconds <= 180
    assert recommendation.story_complexity.scene_count >= 3
    assert recommendation.story_complexity.estimated_asset_count >= 4
    assert fake.calls == 0


def test_master_and_rough_storyboard_require_separate_approval_gates() -> None:
    payload = request()
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake)
    recommendation = service.recommend(payload)
    master_stage = service.generate_master_script(
        payload,
        recommendation,
        confirmation(recommendation),
    )

    with pytest.raises(VideoPreproductionError) as missing_master_approval:
        service.generate_rough_storyboard(master_stage, None)

    assert missing_master_approval.value.code == "MASTER_SCRIPT_APPROVAL_REQUIRED"
    assert fake.calls == 1
    master_approval = approval(
        "master_script",
        master_stage.master_script.master_script_key,
        master_stage.master_script,
    )
    rough_stage = service.generate_rough_storyboard(master_stage, master_approval)

    with pytest.raises(VideoPreproductionError) as missing_rough_approval:
        service.generate_package(payload, rough_stage, None)

    assert missing_rough_approval.value.code == "ROUGH_STORYBOARD_APPROVAL_REQUIRED"

    broken_master_approval = master_approval.model_copy(update={"subject_hash": "f" * 64})
    broken_stage = rough_stage.model_copy(update={"master_script_approval": broken_master_approval})
    with pytest.raises(VideoPreproductionError) as invalid_master_approval:
        service.generate_package(
            payload,
            broken_stage,
            approval(
                "rough_storyboard",
                rough_stage.rough_storyboard.rough_storyboard_key,
                rough_stage.rough_storyboard,
            ),
        )

    assert invalid_master_approval.value.code == "MASTER_SCRIPT_APPROVAL_REQUIRED"


def test_story_and_server_price_facts_change_duration_and_cost_recommendations() -> None:
    service = VideoPreproductionService(ScriptedDeterministicTextFake())
    baseline = service.recommend(request())
    complex_story = service.recommend(
        request(
            creative_concept="多场景连续动作与可见变化。" * 20,
            course_anchor="课程锚点需要在多次状态转换后出现。" * 12,
        )
    )
    expensive = service.recommend(
        request(
            pricing=PricingSnapshot(
                version="video-pricing-2026-08",
                currency="CNY",
                image_candidate_unit_price=Decimal("2.00"),
                candidates_per_asset=2,
            )
        )
    )

    assert complex_story.story_complexity.scene_count > baseline.story_complexity.scene_count
    assert complex_story.story_complexity.estimated_asset_count > (
        baseline.story_complexity.estimated_asset_count
    )
    assert complex_story.recommended_duration_seconds > baseline.recommended_duration_seconds
    assert complex_story.estimated_cost > baseline.estimated_cost
    assert expensive.pricing_version == "video-pricing-2026-08"
    assert expensive.recommended_duration_seconds < baseline.recommended_duration_seconds
    assert expensive.estimated_cost > baseline.estimated_cost


def test_package_is_deterministic_reviewable_and_contains_all_asset_categories() -> None:
    first, first_fake, *_ = build_package()
    second, second_fake, *_ = build_package()

    assert first == second
    assert first.validation_report.valid is True
    assert first.master_script_approval.subject_kind == "master_script"
    assert first.rough_storyboard_approval.subject_kind == "rough_storyboard"
    assert first.master_script.course_anchor == first.source_snapshot.course_anchor
    assert {asset.asset_type for asset in first.asset_inventory.assets} == {
        "character",
        "scene",
        "prop",
        "creature",
    }
    assert first.production_plan.kind == "image_prompts_only"
    assert first.production_plan.media_operations == ()
    assert canonical_package_hash(first) == first.canonical_hash
    assert first_fake.calls == second_fake.calls == 1


def test_validator_rejects_identity_topology_and_continuity_drift() -> None:
    package, *_ = build_package()
    first_scene = package.master_script.scenes[0]
    second_scene = package.master_script.scenes[1]
    broken_scenes = (
        first_scene,
        second_scene.model_copy(update={"position": 1, "start_state": "unlinked"}),
        *package.master_script.scenes[2:],
    )
    broken_master = package.master_script.model_copy(
        update={
            "selected_intro_snapshot_id": "wrong-snapshot",
            "course_anchor": "wrong-anchor",
            "scenes": broken_scenes,
        }
    )
    broken_beat = package.rough_storyboard.beats[0].model_copy(
        update={"scene_key": "missing-scene", "position": 2}
    )
    broken_rough = package.rough_storyboard.model_copy(
        update={"beats": (broken_beat, *package.rough_storyboard.beats[1:])}
    )
    mutated = package.model_copy(
        update={"master_script": broken_master, "rough_storyboard": broken_rough}
    )

    report = validate_package(mutated)

    assert report.valid is False
    assert "master script snapshot identity does not match" in report.errors
    assert "master script course anchor does not match" in report.errors
    assert "master scene positions must be unique and contiguous" in report.errors
    assert "master scene states must be continuous" in report.errors
    assert "rough beat positions must be unique and contiguous" in report.errors
    assert "rough beat references an unknown scene" in report.errors


def test_validator_rejects_incomplete_asset_and_prompt_graph() -> None:
    package, *_ = build_package()
    assets_without_creature = tuple(
        asset for asset in package.asset_inventory.assets if asset.asset_type != "creature"
    )
    bad_asset = assets_without_creature[0].model_copy(
        update={"source_beat_keys": ("missing-beat",)}
    )
    inventory = package.asset_inventory.model_copy(
        update={"assets": (bad_asset, *assets_without_creature[1:])}
    )
    first_prompt = package.production_plan.image_prompts[0]
    bad_prompt = first_prompt.model_copy(
        update={"aspect_ratio": "9:16", "negative_constraints": ()}
    )
    plan = package.production_plan.model_copy(
        update={
            "image_prompts": (bad_prompt, bad_prompt, *package.production_plan.image_prompts[2:])
        }
    )

    report = validate_package(
        package.model_copy(update={"asset_inventory": inventory, "production_plan": plan})
    )

    assert report.valid is False
    assert "asset inventory must contain all four asset categories" in report.errors
    assert "asset source references an unknown beat" in report.errors
    assert "image prompt asset keys must be unique" in report.errors
    assert "image prompts must use the visual plan aspect ratio" in report.errors
    assert "image prompts must retain visual plan negative constraints" in report.errors


def test_canonical_hash_is_byte_equivalent_and_detects_tampering() -> None:
    package, *_ = build_package()
    round_tripped = package.model_validate_json(package.model_dump_json(indent=2))

    assert canonical_package_hash(round_tripped) == package.canonical_hash

    tampered = package.model_copy(
        update={"master_script": package.master_script.model_copy(update={"title": "tampered"})}
    )
    report = validate_package(tampered)

    assert report.valid is False
    assert "canonical hash does not match package content" in report.errors
