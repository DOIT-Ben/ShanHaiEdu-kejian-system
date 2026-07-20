from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.api.video_preproduction.fake import ScriptedDeterministicTextFake
from apps.api.video_preproduction.models import (
    IntroSelectionSnapshot,
    PricingSnapshot,
    TeacherConfirmation,
    VideoPreproductionRequest,
)
from apps.api.video_preproduction.service import (
    VideoPreproductionError,
    VideoPreproductionService,
)
from apps.api.video_preproduction.validator import validate_package


def request(*, pricing: PricingSnapshot | None = None) -> VideoPreproductionRequest:
    return VideoPreproductionRequest(
        intro_selection_snapshot=IntroSelectionSnapshot(
            snapshot_id="intro-selection-001",
            version="1",
            option_key="INTRO-APP-01",
            title="机器人补给舱装载",
            creative_concept="机器人逐个核对补给盒与卡槽的一一对应。",
            hook="舱门即将关闭, 扫描灯提示一个卡槽状态不明。",
            course_anchor="五个卡槽已占用但没有数字标签。",
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
        teacher_confirmation=TeacherConfirmation(
            pricing_version="video-pricing-2026-07",
            currency="CNY",
            confirmed_duration_seconds=90,
            confirmed_estimated_cost=Decimal("8.00"),
            confirmed_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
        ),
    )


def test_service_builds_a_deterministic_reviewable_preproduction_package() -> None:
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake)

    first = service.generate(request())
    second = service.generate(request())

    assert first == second
    assert first.validation_report.valid is True
    assert first.source_snapshot.snapshot_id == "intro-selection-001"
    assert first.teacher_confirmation.pricing_version == "video-pricing-2026-07"
    assert first.master_script.target_duration_seconds == 90
    assert first.master_script.ends_at_handoff is True
    assert first.rough_storyboard.total_duration_seconds == 90
    assert first.visual_plan.aspect_ratio == "16:9"
    assert first.visual_plan.language == "zh-CN"
    assert first.asset_inventory.assets
    assert first.production_plan.kind == "image_prompts_only"
    assert first.production_plan.media_operations == ()
    assert first.production_plan.image_prompts
    assert len(first.canonical_hash) == 64
    assert fake.calls == 2


def test_service_rejects_missing_versioned_pricing_before_text_generation() -> None:
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake)
    payload = request()
    missing_pricing = payload.model_copy(update={"pricing_snapshot": None})

    with pytest.raises(VideoPreproductionError) as caught:
        service.generate(missing_pricing)

    assert caught.value.code == "PRICING_SNAPSHOT_REQUIRED"
    assert fake.calls == 0


def test_service_rejects_unconfirmed_duration_and_cost_before_rough_storyboard() -> None:
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake)
    payload = request()
    unconfirmed = payload.model_copy(
        update={
            "teacher_confirmation": TeacherConfirmation(
                pricing_version="video-pricing-2026-07",
                currency="CNY",
                confirmed_duration_seconds=120,
                confirmed_estimated_cost=Decimal("8.00"),
                confirmed_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
            )
        }
    )

    with pytest.raises(VideoPreproductionError) as caught:
        service.generate(unconfirmed)

    assert caught.value.code == "TEACHER_CONFIRMATION_REQUIRED"
    assert fake.calls == 0


def test_service_recommends_duration_and_cost_from_the_pricing_snapshot() -> None:
    expensive_pricing = PricingSnapshot(
        version="video-pricing-2026-08",
        currency="CNY",
        image_candidate_unit_price=Decimal("2.00"),
        candidates_per_asset=2,
    )
    payload = request(pricing=expensive_pricing).model_copy(
        update={
            "teacher_confirmation": TeacherConfirmation(
                pricing_version="video-pricing-2026-08",
                currency="CNY",
                confirmed_duration_seconds=75,
                confirmed_estimated_cost=Decimal("20.00"),
                confirmed_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
            )
        }
    )

    package = VideoPreproductionService(ScriptedDeterministicTextFake()).generate(payload)

    assert package.duration_recommendation.recommended_duration_seconds == 75
    assert package.duration_recommendation.estimated_cost == Decimal("20.00")
    assert package.rough_storyboard.total_duration_seconds == 75


def test_validator_rejects_a_script_that_preteaches_the_selected_boundary() -> None:
    package = VideoPreproductionService(ScriptedDeterministicTextFake()).generate(request())
    preteaching_script = package.master_script.model_copy(
        update={"complete_story": "机器人直接讲解比较大小。"}
    )

    report = validate_package(package.model_copy(update={"master_script": preteaching_script}))

    assert report.valid is False
    assert report.errors == ("master script must not preteach: 比较大小",)
