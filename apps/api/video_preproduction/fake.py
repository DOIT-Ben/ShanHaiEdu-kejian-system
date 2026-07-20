"""Scripted deterministic text fake for video preproduction tests and CI."""

from __future__ import annotations

from dataclasses import dataclass

from apps.api.video_preproduction.models import IntroSelectionSnapshot, MasterScene, MasterScript


@dataclass(frozen=True, slots=True)
class ScriptedDeterministicTextFake:
    """Produces a reviewable script without a model gateway or Provider call."""

    calls: int = 0

    def generate_master_script(
        self,
        snapshot: IntroSelectionSnapshot,
        *,
        target_duration_seconds: int,
        scene_count: int,
    ) -> MasterScript:
        object.__setattr__(self, "calls", self.calls + 1)
        durations = _split_duration(target_duration_seconds, scene_count)
        scenes = tuple(
            _scene(snapshot, position, scene_count, durations[position - 1])
            for position in range(1, scene_count + 1)
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
            target_duration_seconds=target_duration_seconds,
            ends_at_handoff=True,
        )


def _scene(
    snapshot: IntroSelectionSnapshot,
    position: int,
    scene_count: int,
    duration_seconds: int,
) -> MasterScene:
    start_state = snapshot.hook if position == 1 else f"story-state-{position - 1}"
    end_state = snapshot.handoff_moment if position == scene_count else f"story-state-{position}"
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
        narration=narration,
        start_state=start_state,
        end_state=end_state,
        duration_seconds=duration_seconds,
    )


def _split_duration(total_seconds: int, count: int) -> tuple[int, ...]:
    quotient, remainder = divmod(total_seconds, count)
    return tuple(quotient + (1 if position < remainder else 0) for position in range(count))
