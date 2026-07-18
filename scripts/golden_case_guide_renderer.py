# ruff: noqa: RUF001
"""Render the numbers 1-to-5 golden fixture as a product-readable example."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from scripts.generation_guide_renderer import cell, display, generated_header, yes_no

SECTION_LABELS = {
    "teaching_content": "一、教学内容",
    "material_analysis": "二、教材分析",
    "learner_analysis": "三、学情分析",
    "design_intent": "四、设计意图",
    "teaching_objectives": "五、教学目标",
    "key_difficulties_and_strategies": "六、教学重难点及突破策略",
    "preparation": "七、教学准备",
    "teaching_process": "八、教学过程",
    "board_design": "九、板书设计",
    "lesson_summary": "十、课堂总结",
    "differentiated_homework": "十一、分层作业",
    "teaching_reflection": "十二、教学反思",
}


def _summary(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "待教师实教后填写"
        return "；".join(_summary(item) for item in value[:3])
    if not isinstance(value, dict):
        if value == "not_taught":
            return "尚未授课，保留反思问题，待教师课后填写"
        return display(value)
    preferred = (
        "topic",
        "current_focus",
        "teaching_main_line",
        "observable_outcome",
        "key_learning_focus",
        "title",
        "task",
        "layout",
        "teacher_closure",
        "state",
    )
    for key in preferred:
        if key in value:
            return _summary(value[key])
    first_key = next(iter(value), None)
    return _summary(value[first_key]) if first_key else "无"


def _render_lesson(golden: Mapping[str, Any]) -> list[str]:
    division = cast(Mapping[str, Any], golden["lesson_division"])
    lesson = cast(Mapping[str, Any], golden["lesson_plan"])
    units = cast(list[dict[str, Any]], division["lesson_units"])
    sections = cast(Mapping[str, Any], lesson["sections"])
    lines = [
        "## 3. 课时划分与教案示例",
        "",
        "| 课时 | 时长 | 核心学习结果 | 讲授边界 |",
        "| --- | --- | --- | --- |",
    ]
    for unit in units:
        lines.append(
            f"| {cell(unit['title'])} | {unit['duration_minutes']} 分钟 | "
            f"{cell(unit['core_learning_outcome'])} | {cell(unit['content_boundary'])} |"
        )
    lines.extend(["", "十二部分教案的黄金内容摘要：", "", "| 部分 | 示例内容 |", "| --- | --- |"])
    for key, label in SECTION_LABELS.items():
        lines.append(f"| {label} | {cell(_summary(sections[key]))} |")
    return [*lines, ""]


def _render_intro(golden: Mapping[str, Any]) -> list[str]:
    option_set = cast(Mapping[str, Any], golden["intro_option_set"])
    selection = cast(Mapping[str, Any], golden["intro_selection"])
    labels = {"science": "科学", "application": "应用", "story": "故事"}
    medium_labels = {"video": "视频", "mixed": "混合媒介", "performance": "课堂表演"}
    lines = [
        "## 4. 三类九套示例",
        "",
        "| 类别 | 方案 | 媒介/时长 | 推荐分 | 最小课程锚点 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for option in cast(list[dict[str, Any]], option_set["options"]):
        medium = f"{medium_labels[option['suggested_medium']]} / {option['duration_seconds']} 秒"
        lines.append(
            f"| {labels[option['category']]} | {cell(option['title'])} | {medium} | "
            f"{option['recommendation_score']} | {cell(option['course_anchor'])} |"
        )
    snapshot = cast(Mapping[str, Any], selection["snapshot"])
    lines.extend(
        [
            "",
            f"**最终选择：** `{selection['option_key']}`《{snapshot['title']}》，"
            f"首个课堂问题是“{snapshot['classroom_first_question']}”。",
            "",
        ]
    )
    return lines


def _render_ppt(golden: Mapping[str, Any]) -> list[str]:
    ppt = cast(Mapping[str, Any], golden["ppt"])
    page_type_labels = {
        "cover": "封面",
        "introduction": "导入",
        "exploration": "探索",
        "concept": "概念",
        "discussion": "讨论",
        "practice": "练习",
        "summary": "总结",
    }
    lines = [
        "## 5. 10 页 PPT 示例",
        "",
        "| 页码 | 页面类型 | 教学任务 | 主视觉 |",
        "| --- | --- | --- | --- |",
    ]
    for page in cast(list[dict[str, Any]], ppt["page_specs"]):
        visual = cast(Mapping[str, Any], page["main_visual"])
        page_type = f"{page_type_labels[page['page_type']]} (`{page['page_type']}`)"
        lines.append(
            f"| {page['position']} | {page_type} | {cell(page['teaching_task'])} "
            f"| {cell(visual['description'])} |"
        )
    style = cast(Mapping[str, Any], ppt["style_contract"])
    lines.extend(
        [
            "",
            f"**统一风格：** {style['typography']} 正文背景固定为 "
            f"`{style['body_background_color']}`；AI 图片不烘焙准确文字、数字和公式。",
            "",
        ]
    )
    return lines


def _render_video_header(video: Mapping[str, Any]) -> list[str]:
    master = cast(Mapping[str, Any], video["master_script"])
    rough = cast(Mapping[str, Any], video["rough_storyboard"])
    lines = [
        "## 6. 50 秒视频示例",
        "",
        f"**标题：**《{master['title']}》  **叙事目的：** {master['narrative_purpose']}",
        "",
        "| 节拍 | 时长 | 主要事件 |",
        "| --- | --- | --- |",
    ]
    for beat in cast(list[dict[str, Any]], rough["beats"]):
        lines.append(
            f"| `{beat['beat_key']}` | {beat['duration_seconds']} 秒 | "
            f"{cell(beat['primary_event'])} |"
        )
    return lines


def _render_video_assets(video: Mapping[str, Any]) -> list[str]:
    inventory = cast(Mapping[str, Any], video["asset_inventory"])
    asset_type_labels = {
        "character": "角色",
        "scene": "场景",
        "prop": "道具",
        "creature": "生物",
    }
    lines = [
        "",
        "四类资产（本例没有生物类）：",
        "",
        "| 类型 | 资产 | 用途 |",
        "| --- | --- | --- |",
    ]
    for asset in cast(list[dict[str, Any]], inventory["assets"]):
        asset_type = f"{asset_type_labels[asset['asset_type']]} (`{asset['asset_type']}`)"
        lines.append(f"| {asset_type} | {cell(asset['name'])} | {cell(asset['usage'])} |")
    return lines


def _render_video_shots(video: Mapping[str, Any]) -> list[str]:
    fine = cast(Mapping[str, Any], video["fine_storyboard"])
    lines = ["", "镜头级真实生成指令示例：", ""]
    for shot in cast(list[dict[str, Any]], fine["shots"]):
        lines.extend(
            [
                f"### {shot['shot_key']}（{shot['duration_seconds']} 秒）",
                "",
                f"- 可见变化：{shot['visible_beat']}",
                f"- 起止状态：{shot['start_state']} → {shot['end_state']}",
                f"- 完整指令：{shot['prompt_text']}",
                f"- 课堂交接镜头：{yes_no(shot['handoff_marker'])}",
                "",
            ]
        )
    return lines


def _render_audio(video: Mapping[str, Any]) -> list[str]:
    audio = cast(Mapping[str, Any], video["audio_plan"])
    kind_labels = {"narration": "旁白", "sound_effect": "音效", "music": "配乐"}
    lines = ["音频轨道：", "", "| 类型 | 时间 | 内容 |", "| --- | --- | --- |"]
    for track in cast(list[dict[str, Any]], audio["tracks"]):
        timeline = cast(Mapping[str, Any], track["timeline"])
        kind = f"{kind_labels[track['kind']]} (`{track['kind']}`)"
        lines.append(
            f"| {kind} | {timeline['start_seconds']}–{timeline['end_seconds']} 秒 "
            f"| {cell(track['script_text'])} |"
        )
    return [*lines, ""]


def _render_video(golden: Mapping[str, Any]) -> list[str]:
    video = cast(Mapping[str, Any], golden["video"])
    return [
        *_render_video_header(video),
        *_render_video_assets(video),
        *_render_video_shots(video),
        *_render_audio(video),
    ]


def render_golden_case(golden: Mapping[str, Any]) -> str:
    source = cast(Mapping[str, Any], golden["source"])
    project = cast(Mapping[str, Any], golden["project"])
    preferences = cast(Mapping[str, Any], golden["teacher_preferences"])
    boundary = cast(Mapping[str, Any], golden["knowledge_boundary"])
    project_line = (
        f"- 项目：{project['grade']}《{project['topic']}》，"
        f"{project['lesson_duration_minutes']} 分钟。"
    )
    mode_line = (
        f"- 执行方式：`{preferences['execution_mode']}`；PPT "
        f"{preferences['ppt_aspect_ratio']} / {preferences['ppt_preferred_page_count']} 页；"
        f"视频 {preferences['video_target_duration_seconds']} 秒。"
    )
    lines = generated_header("“1～5的认识”黄金测试示例")
    lines.extend(
        [
            "Fixture 不代表真实媒体已经生成；它固定的是输入、结构、提示词、依赖和质量预期。",
            "",
            "## 1. 教材与项目输入",
            "",
            f"- 教材：`{source['file_name']}`，共 {source['pdf_page_count']} 页。",
            "- 黄金范围：物理页 3～5，对应印刷页 14～16。",
            f"- SHA-256：`{source['sha256']}`。原教材不提交仓库。",
            project_line,
            mode_line,
            "",
            "## 2. 知识边界",
            "",
            f"- 必须教：{display(boundary['must_teach'])}。",
            f"- 可以练：{display(boundary['may_practice'])}。",
            f"- 不得提前教：{display(boundary['must_not_preteach'])}。",
            "",
            *_render_lesson(golden),
            *_render_intro(golden),
            *_render_ppt(golden),
            *_render_video(golden),
            "## 7. 阶段验收边界",
            "",
            "- 普通 CI：只运行确定性 Fake 和合同测试。",
            "- 媒体阶段出口：必须补真实文本、图片、视频和 TTS 冒烟。",
            "- 当前示例不会伪装成已生成 DOCX、PPTX、图片、音频或 MP4。",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
