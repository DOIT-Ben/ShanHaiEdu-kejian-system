from __future__ import annotations

import pytest

from apps.api.video_preproduction.fake import ScriptedDeterministicTextFake
from apps.api.video_preproduction.models import (
    IntroSelectionSnapshot,
    MasterScript,
    SceneAssetRequirement,
)
from apps.api.video_preproduction.service import (
    VideoPreproductionError,
    VideoPreproductionService,
)
from apps.api.video_preproduction.validator import (
    canonical_package_bytes,
    canonical_package_hash,
    validate_package,
)
from tests.unit.video_preproduction.helpers import (
    NOW,
    approval,
    build_package,
    confirmation,
    request,
)


class StaticGenerator:
    def __init__(self, master: MasterScript) -> None:
        self.master = master

    def generate_master_script(self, snapshot: IntroSelectionSnapshot) -> MasterScript:
        return self.master


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


def test_one_asset_identity_cannot_expand_to_multiple_generation_keys() -> None:
    payload = request()
    master = ScriptedDeterministicTextFake().generate_master_script(
        payload.intro_selection_snapshot
    )
    scene = master.scenes[0]
    duplicate = scene.asset_requirements[0].model_copy(
        update={"asset_key": "asset-character-duplicate"}
    )
    invalid_master = master.model_copy(
        update={
            "scenes": (
                scene.model_copy(
                    update={"asset_requirements": (*scene.asset_requirements, duplicate)}
                ),
                *master.scenes[1:],
            )
        }
    )
    service = VideoPreproductionService(StaticGenerator(invalid_master), clock=lambda: NOW)

    with pytest.raises(VideoPreproductionError) as caught:
        service.generate_master_script(payload)

    assert caught.value.code == "VIDEO_MASTER_SCRIPT_INVALID"


def test_pricing_inventory_and_handoff_use_the_same_story_asset_facts() -> None:
    payload = request()
    baseline = ScriptedDeterministicTextFake().generate_master_script(
        payload.intro_selection_snapshot
    )
    creature = SceneAssetRequirement(
        asset_key="asset-creature-helper",
        asset_type="creature",
        identity_key="story-creature-helper",
        purpose="陪同机器人检查补给舱。",
        visual_description="一只小型机械助手, 银色外壳与蓝色扫描灯。",
    )
    first_scene = baseline.scenes[0].model_copy(
        update={"asset_requirements": (*baseline.scenes[0].asset_requirements, creature)}
    )
    master = baseline.model_copy(update={"scenes": (first_scene, *baseline.scenes[1:])})
    service = VideoPreproductionService(StaticGenerator(master), clock=lambda: NOW)
    master_stage = service.generate_master_script(payload)
    recommendation = service.recommend(payload, master_stage)

    assert recommendation.story_complexity.estimated_asset_count == 6
    assert payload.pricing_snapshot is not None
    assert recommendation.estimated_cost == (
        payload.pricing_snapshot.image_candidate_unit_price
        * payload.pricing_snapshot.candidates_per_asset
        * 6
    )
    assert all(
        payload.intro_selection_snapshot.classroom_first_question not in scene.dialogue
        for scene in master_stage.master_script.scenes
    )

    confirmed = confirmation(recommendation)
    master_approval = approval(
        "master_script",
        master.master_script_key,
        master,
        confirmation_fact=confirmed,
    )
    rough_stage = service.generate_rough_storyboard(
        payload,
        master_stage,
        recommendation,
        confirmed,
        master_approval,
    )
    package = service.generate_package(
        payload,
        rough_stage,
        approval(
            "rough_storyboard",
            rough_stage.rough_storyboard.rough_storyboard_key,
            rough_stage.rough_storyboard,
        ),
    )

    assert len(package.asset_inventory.creatures) == 1
    assert (
        sum(
            len(group)
            for group in (
                package.asset_inventory.characters,
                package.asset_inventory.scenes,
                package.asset_inventory.props,
                package.asset_inventory.creatures,
            )
        )
        == recommendation.story_complexity.estimated_asset_count
    )


def test_master_rejects_the_post_handoff_classroom_question_as_dialogue() -> None:
    payload = request()
    master = ScriptedDeterministicTextFake().generate_master_script(
        payload.intro_selection_snapshot
    )
    final_scene = master.scenes[-1].model_copy(
        update={"dialogue": payload.intro_selection_snapshot.classroom_first_question}
    )
    invalid = master.model_copy(update={"scenes": (*master.scenes[:-1], final_scene)})
    service = VideoPreproductionService(StaticGenerator(invalid), clock=lambda: NOW)

    with pytest.raises(VideoPreproductionError) as caught:
        service.generate_master_script(payload)

    assert caught.value.code == "VIDEO_MASTER_SCRIPT_INVALID"
