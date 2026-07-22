"""Scripted deterministic text fake for video preproduction tests and CI."""

from __future__ import annotations

from dataclasses import dataclass

from apps.api.video_preproduction.models import (
    IntroSelectionSnapshot,
    MasterScene,
    MasterScript,
    SceneAssetRequirement,
)


@dataclass(frozen=True, slots=True)
class ScriptedDeterministicTextFake:
    """Produces a reviewable script without a model gateway or Provider call."""

    calls: int = 0

    def generate_master_script(self, snapshot: IntroSelectionSnapshot) -> MasterScript:
        object.__setattr__(self, "calls", self.calls + 1)
        scene_count = _scene_count(snapshot)
        scenes = tuple(
            _scene(snapshot, position, scene_count) for position in range(1, scene_count + 1)
        )
        return MasterScript(
            master_script_key=f"master-{snapshot.snapshot_id}",
            selected_intro_snapshot_id=snapshot.snapshot_id,
            selected_intro_snapshot_version=snapshot.version,
            selected_intro_option_key=snapshot.option_key,
            title=snapshot.title,
            creative_concept=snapshot.creative_concept,
            course_anchor=snapshot.course_anchor,
            narrative_purpose="以可见变化引出课堂首问。",
            complete_story=" ".join(scene.narration for scene in scenes),
            scenes=scenes,
            ends_at_handoff=True,
        )


def _scene_count(snapshot: IntroSelectionSnapshot) -> int:
    story_chars = len(snapshot.creative_concept.strip()) + len(snapshot.course_anchor.strip())
    return min(6, max(3, 2 + (story_chars + 79) // 80))


def _scene(
    snapshot: IntroSelectionSnapshot,
    position: int,
    scene_count: int,
) -> MasterScene:
    start_state = snapshot.hook if position == 1 else f"story-state-{position - 1}"
    end_state = snapshot.handoff_moment if position == scene_count else f"story-state-{position}"
    visible_beats = (
        f"第{position}场建立清楚的观察对象。",
        f"第{position}场完成一次可见状态变化。",
    )
    if position == 1:
        narration = f"{snapshot.creative_concept} {snapshot.hook}"
    elif position == scene_count:
        narration = f"{snapshot.course_anchor} {snapshot.handoff_moment}"
    else:
        narration = f"第{position}场通过可见动作推进核对, 暂不公布课程结论。"
    return MasterScene(
        scene_key=f"scene-{position}",
        position=position,
        purpose=f"推进故事结构第{position}场。",
        location=f"围绕“{snapshot.course_anchor}”建立的第{position}个故事空间。",
        action=f"按创意概念执行可见动作: {snapshot.creative_concept}",
        visible_change=f"可见状态从第{position - 1}阶段推进到第{position}阶段。",
        visible_beats=visible_beats,
        estimated_shot_count=len(visible_beats),
        narration=narration,
        dialogue=(
            "画面在交接点停止, 等待教师接回课堂。"
            if position == scene_count
            else "角色确认当前变化。"
        ),
        sound_intent=f"第{position}场用清晰节奏提示可见状态变化。",
        start_state=start_state,
        end_state=end_state,
        asset_requirements=_asset_requirements(snapshot, position),
    )


def _asset_requirements(
    snapshot: IntroSelectionSnapshot,
    position: int,
) -> tuple[SceneAssetRequirement, ...]:
    return (
        SceneAssetRequirement(
            asset_key="asset-character",
            asset_type="character",
            identity_key="story-character",
            purpose="承载故事主要行动。",
            visual_description=f"创意概念中的主要行动者: {snapshot.creative_concept}",
        ),
        SceneAssetRequirement(
            asset_key=f"asset-scene-{position}",
            asset_type="scene",
            identity_key=f"story-scene-{position}",
            purpose=f"呈现第{position}场空间与状态变化。",
            visual_description=(
                f"围绕课程锚点“{snapshot.course_anchor}”的第{position}场完整环境, "
                f"起始于“{snapshot.hook}”。"
            ),
        ),
        SceneAssetRequirement(
            asset_key="asset-prop",
            asset_type="prop",
            identity_key="story-core-prop",
            purpose="承载贯穿故事的核心可见变化。",
            visual_description=f"创意概念中的核心道具与状态: {snapshot.creative_concept}",
        ),
    )
