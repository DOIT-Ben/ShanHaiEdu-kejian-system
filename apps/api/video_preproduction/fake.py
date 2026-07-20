"""Scripted deterministic text fake for video preproduction tests and CI."""

from __future__ import annotations

from dataclasses import dataclass

from apps.api.video_preproduction.models import IntroSelectionSnapshot, MasterScene, MasterScript


@dataclass(frozen=True, slots=True)
class ScriptedDeterministicTextFake:
    """Produces a fixed, reviewable script without a model gateway call."""

    calls: int = 0

    def generate_master_script(
        self,
        snapshot: IntroSelectionSnapshot,
        *,
        target_duration_seconds: int,
    ) -> MasterScript:
        object.__setattr__(self, "calls", self.calls + 1)
        scene_durations = _split_duration(target_duration_seconds)
        scenes = (
            MasterScene(
                scene_key="scene-setup",
                position=1,
                purpose="建立待核对的补给舱情境。",
                visible_change="补给盒与卡槽同时进入画面。",
                narration=snapshot.hook,
                start_state="舱门未关闭。",
                end_state="扫描灯提示存在待核对状态。",
                duration_seconds=scene_durations[0],
            ),
            MasterScene(
                scene_key="scene-check",
                position=2,
                purpose="让学生观察一一对应的核对过程。",
                visible_change="机器人逐个核对补给盒与卡槽。",
                narration="每个补给盒都对应一个清楚的卡槽, 机器人暂不报出数量。",
                start_state="存在待核对状态。",
                end_state="补给盒与卡槽逐一对齐。",
                duration_seconds=scene_durations[1],
            ),
            MasterScene(
                scene_key="scene-handoff",
                position=3,
                purpose="在课堂问题前停住故事。",
                visible_change="核对完成, 机器人准备重新扫描。",
                narration=snapshot.handoff_moment,
                start_state="补给盒与卡槽逐一对齐。",
                end_state=snapshot.handoff_moment,
                duration_seconds=scene_durations[2],
            ),
        )
        return MasterScript(
            master_script_key=f"master-{snapshot.snapshot_id}",
            selected_intro_snapshot_id=snapshot.snapshot_id,
            title=snapshot.title,
            narrative_purpose="以可见的一一对应核对过程引出课堂首问。",
            complete_story=" ".join(scene.narration for scene in scenes),
            scenes=scenes,
            target_duration_seconds=target_duration_seconds,
            ends_at_handoff=True,
        )


def _split_duration(total_seconds: int) -> tuple[int, int, int]:
    first = total_seconds // 3
    second = total_seconds // 3
    return first, second, total_seconds - first - second
