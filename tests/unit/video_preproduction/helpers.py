"""Shared deterministic facts for video preproduction unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

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
from apps.api.video_preproduction.service import VideoPreproductionService
from apps.api.video_preproduction.validator import canonical_fact_hash

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
    approved_at: datetime = NOW,
) -> ApprovalFact:
    return ApprovalFact(
        subject_kind=subject_kind,
        subject_key=subject_key,
        subject_hash=canonical_fact_hash(value),
        confirmation_hash=(
            canonical_fact_hash(confirmation_fact) if confirmation_fact is not None else None
        ),
        approved_by="teacher-001",
        approved_at=approved_at,
    )


def build_package(*, payload: VideoPreproductionRequest | None = None):
    selected = payload or request()
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake, clock=lambda: NOW)
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
