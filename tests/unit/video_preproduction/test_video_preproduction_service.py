from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import get_type_hints

import pytest

from apps.api.video_preproduction.asset_planning import inventory_assets
from apps.api.video_preproduction.fake import ScriptedDeterministicTextFake
from apps.api.video_preproduction.models import (
    IntroSelectionSnapshot,
    MasterScript,
    PricingSnapshot,
)
from apps.api.video_preproduction.ports import VideoPreproductionTextGenerator
from apps.api.video_preproduction.service import (
    VideoPreproductionError,
    VideoPreproductionService,
)
from apps.api.video_preproduction.validator import (
    validate_package,
)
from tests.unit.video_preproduction.helpers import (
    NOW,
    approval,
    build_package,
    confirmation,
    request,
)


def test_master_precedes_story_based_recommendation_and_teacher_confirmation() -> None:
    payload = request()
    fake = ScriptedDeterministicTextFake()
    service = VideoPreproductionService(fake, clock=lambda: NOW)
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
    service = VideoPreproductionService(generator, clock=lambda: NOW)

    stage = service.generate_master_script(request())

    assert generator.calls == 1
    assert stage.master_script.selected_intro_snapshot_id == stage.source_snapshot.snapshot_id
    hints = get_type_hints(VideoPreproductionService.__init__)
    assert hints["text_generator"] is VideoPreproductionTextGenerator


def test_rough_storyboard_requires_confirmation_and_master_approval() -> None:
    payload = request()
    service = VideoPreproductionService(ScriptedDeterministicTextFake(), clock=lambda: NOW)
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


def test_package_rejects_rough_approval_before_storyboard_generation() -> None:
    _, _, service, payload, _, _, rough_stage = build_package()
    early = approval(
        "rough_storyboard",
        rough_stage.rough_storyboard.rough_storyboard_key,
        rough_stage.rough_storyboard,
        approved_at=rough_stage.rough_storyboard.generated_at - timedelta(seconds=1),
    )

    with pytest.raises(VideoPreproductionError) as caught:
        service.generate_package(payload, rough_stage, early)

    assert caught.value.code == "ROUGH_STORYBOARD_APPROVAL_REQUIRED"


def test_story_structure_and_server_price_facts_change_recommendations() -> None:
    service = VideoPreproductionService(ScriptedDeterministicTextFake(), clock=lambda: NOW)
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


def test_nested_master_and_rough_text_cannot_hide_preteaching() -> None:
    payload = request()
    baseline = ScriptedDeterministicTextFake().generate_master_script(
        payload.intro_selection_snapshot
    )
    scene = baseline.scenes[0].model_copy(
        update={"visible_beats": ("这里提前讲出比较大小", *baseline.scenes[0].visible_beats[1:])}
    )

    class ForbiddenGenerator:
        def generate_master_script(self, snapshot: IntroSelectionSnapshot) -> MasterScript:
            return baseline.model_copy(update={"scenes": (scene, *baseline.scenes[1:])})

    service = VideoPreproductionService(ForbiddenGenerator(), clock=lambda: NOW)

    with pytest.raises(VideoPreproductionError) as caught:
        service.generate_master_script(payload)

    assert caught.value.code == "VIDEO_MASTER_SCRIPT_INVALID"


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
    combined_prompts = " ".join(prompt.prompt for prompt in package.production_plan.image_prompts)
    assert "机器人" in combined_prompts
    assert "补给盒" in combined_prompts
    assert "卡槽" in combined_prompts
    for asset in inventory_assets(inventory):
        prompt = next(
            item
            for item in package.production_plan.image_prompts
            if item.asset_key == asset.asset_key
        )
        assert asset.visual_description in prompt.prompt
        assert asset.purpose in prompt.prompt


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


def test_validator_rejects_hidden_rough_preteach_and_asset_semantic_drift() -> None:
    package, *_ = build_package()
    first_beat = package.rough_storyboard.beats[0].model_copy(
        update={"main_event": "提前讲出比较大小"}
    )
    rough = package.rough_storyboard.model_copy(
        update={"beats": (first_beat, *package.rough_storyboard.beats[1:])}
    )
    first_asset = package.asset_inventory.characters[0].model_copy(
        update={"visual_description": "generic placeholder"}
    )
    inventory = package.asset_inventory.model_copy(update={"characters": (first_asset,)})

    report = validate_package(
        package.model_copy(update={"rough_storyboard": rough, "asset_inventory": inventory})
    )

    assert report.valid is False
    assert "rough storyboard must not preteach: 比较大小" in report.errors
    assert "asset inventory must preserve master asset semantics" in report.errors
    assert "image prompts must retain asset visual semantics" in report.errors
