"""Scripted deterministic text fake for video preproduction tests and CI."""

from __future__ import annotations

from dataclasses import dataclass

from apps.api.video_preproduction.models import IntroSelectionSnapshot, MasterScene, MasterScript


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
        visible_change=f"可见状态从第{position - 1}阶段推进到第{position}阶段。",
        visible_beats=visible_beats,
        estimated_shot_count=len(visible_beats),
        narration=narration,
        start_state=start_state,
        end_state=end_state,
    )
