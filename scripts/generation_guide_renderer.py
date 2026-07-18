# ruff: noqa: RUF001
"""Render human-readable generation node chapters from the compact source."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

CHAPTER_NODE_KEYS: dict[str, tuple[str, ...]] = {
    "LESSON.md": (
        "lesson.division.generate",
        "lesson_plan.generate",
    ),
    "INTRO.md": (
        "intro.ideate",
        "intro.anchor",
    ),
    "PPT_DESIGN.md": (
        "ppt.content_analyze",
        "ppt.outline.generate",
        "ppt.pages.generate",
    ),
    "PPT_IMAGES.md": (
        "ppt.cover.prompt.generate",
        "ppt.cover.image.generate",
        "ppt.body_asset_prompts.generate",
        "ppt.body_assets.generate",
    ),
    "VIDEO_SCRIPT_AND_STYLE.md": (
        "video.master_script.generate",
        "video.rough_storyboard.generate",
        "video.style_master.prompt.generate",
        "video.style_master.image.generate",
    ),
    "VIDEO_ASSETS.md": (
        "video.asset_inventory.generate",
        "video.asset_prompts.generate",
        "video.assets.generate",
    ),
    "VIDEO_SHOTS.md": (
        "video.fine_storyboard.generate",
        "video.shots.generate",
    ),
    "AUDIO_AND_QUALITY.md": (
        "audio.plan.generate",
        "audio.tts.generate",
        "video.classroom_quality.evaluate",
    ),
}

CHAPTER_TITLES = {
    "LESSON.md": "课时划分与十二部分教案",
    "INTRO.md": "三类九套与最小课程锚定",
    "PPT_DESIGN.md": "PPT 内容分析、大纲与逐页设计",
    "PPT_IMAGES.md": "PPT 封面与正文图片",
    "VIDEO_SCRIPT_AND_STYLE.md": "视频剧本、粗分镜与视觉母图",
    "VIDEO_ASSETS.md": "视频四类图片资产",
    "VIDEO_SHOTS.md": "视频细分镜与逐镜头生成",
    "AUDIO_AND_QUALITY.md": "音频、TTS 与课堂质量验收",
}

SOURCE_LABELS = {"teacher": "教师填写", "system": "系统设置", "context": "上游自动带入"}


def display(value: Any) -> str:
    if value is None:
        return "未设置"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, list):
        return "、".join(display(item) for item in value) or "无"
    if isinstance(value, dict):
        return "；".join(f"{key}：{display(item)}" for key, item in value.items())
    return str(value)


def cell(value: Any) -> str:
    return display(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def yes_no(value: Any) -> str:
    return "是" if value is True else "否"


def generated_header(title: str) -> list[str]:
    return [
        "<!-- 由 scripts/render_builtin_generation_guide.py 确定性生成，请勿手工修改。 -->",
        "",
        f"# {title}",
        "",
        "本页用于产品负责人、内容管理员和开发者审查后台生成合同，不是教师端界面文案。",
        "",
    ]


def _default_text(field: Mapping[str, Any], options: list[dict[str, Any]]) -> str:
    value = field["default_value"]
    for option in options:
        if option["value"] == value:
            return f"{option['label']} (`{value}`)"
    return display(value)


def _input_notes(field: Mapping[str, Any]) -> str:
    notes: list[str] = []
    if field.get("description"):
        notes.append(cast(str, field["description"]).rstrip("。；; "))
    options = cast(list[dict[str, Any]], field.get("options", []))
    if "default_value" in field:
        notes.append(f"默认：{_default_text(field, options)}")
    if options:
        notes.append("可选：" + "、".join(display(option["label"]) for option in options))
    return "；".join(notes) or "按字段合同填写"


def _render_input_table(node: Mapping[str, Any], sources: set[str]) -> list[str]:
    rows = [
        "| 字段 | 来源 | 必填 | 默认值或说明 |",
        "| --- | --- | --- | --- |",
    ]
    input_spec = cast(Mapping[str, Any], node["input"])
    fields = cast(list[dict[str, Any]], input_spec["fields"])
    selected = [field for field in fields if field["source"] in sources]
    if not selected:
        rows.append("| 无 | 本步骤不要求教师额外填写 | - | - |")
        return rows
    for field in selected:
        source = SOURCE_LABELS[cast(str, field["source"])]
        label = f"{field['label']} (`{field['field_key']}`)"
        rows.append(
            f"| {cell(label)} | {cell(source)} | {yes_no(field['required'])} "
            f"| {cell(_input_notes(field))} |"
        )
    return rows


def _render_context(node: Mapping[str, Any]) -> list[str]:
    prompt = cast(Mapping[str, Any], node["prompt"])
    bindings = cast(list[dict[str, Any]], prompt["context_bindings"])
    if not bindings:
        return ["- 无上游业务 Context；生成所需任务包或参考资产由系统字段带入。"]
    rows = ["| 上游快照 | 是否必须 | 注入范围 |", "| --- | --- | --- |"]
    exposure_labels = {"full": "完整快照", "summary": "摘要"}
    for binding in bindings:
        exposure = exposure_labels.get(binding["exposure"], binding["exposure"])
        rows.append(f"| `{binding['source']}` | {yes_no(binding['required'])} | {cell(exposure)} |")
    return rows


def _output_notes(field: Mapping[str, Any]) -> str:
    notes: list[str] = []
    children = cast(list[dict[str, Any]], field.get("children", []))
    if children:
        notes.append("子字段：" + "、".join(cast(str, child["label"]) for child in children))
    if field.get("generation_instruction"):
        notes.append(cast(str, field["generation_instruction"]))
    return "；".join(notes) or "按结构化合同生成"


def _render_output_table(node: Mapping[str, Any]) -> list[str]:
    rows = [
        "| 输出字段 | 类型 | 必填 | 教师可改 | 内容说明 |",
        "| --- | --- | --- | --- | --- |",
    ]
    output_spec = cast(Mapping[str, Any], node["output"])
    fields = cast(list[dict[str, Any]], output_spec["fields"])
    for field in fields:
        label = f"{field['label']} (`{field['field_key']}`)"
        rows.append(
            f"| {cell(label)} | `{field['type']}` | {yes_no(field['required'])} "
            f"| {yes_no(field['editable'])} | {cell(_output_notes(field))} |"
        )
    return rows


def _render_prompt(node: Mapping[str, Any]) -> list[str]:
    prompt = cast(Mapping[str, Any], node["prompt"])
    parts = (
        ("角色（平台固定）", "role"),
        ("任务（教师可修改）", "task"),
        ("方法（平台固定）", "method"),
        ("质量门禁（平台固定）", "quality_gate"),
    )
    lines: list[str] = []
    for label, key in parts:
        content = str(prompt[key]).replace("\n", " ")
        lines.extend([f"**{label}**", "", f"> {content}", ""])
    return lines


def _render_projection(node: Mapping[str, Any]) -> list[str]:
    projection = cast(Mapping[str, Any], node["projection"])
    return [
        f"- 渲染器：`{projection['renderer_id']}`",
        f"- 教师可见：{yes_no(projection.get('teacher_visible', True))}",
        "",
        "```markdown",
        cast(str, projection["template"]),
        "```",
    ]


def _render_node(node: Mapping[str, Any], position: int) -> list[str]:
    styles = cast(list[str], node.get("style_preset_refs", []))
    style_text = "、".join(f"`{key}`" for key in styles) if styles else "无固定视觉预设"
    return [
        f"## {position}. {node['title']} (`{node['template_key']}`)",
        "",
        f"**做什么：** {node['description']}",
        "",
        f"**逻辑模型能力：** `{node['model_capability']}`  **视觉预设：** {style_text}",
        "",
        "### 教师需要填写",
        "",
        *_render_input_table(node, {"teacher"}),
        "",
        "### 系统自动带入",
        "",
        *_render_input_table(node, {"system", "context"}),
        "",
        *_render_context(node),
        "",
        "### 实际提示词",
        "",
        *_render_prompt(node),
        "### 结构化输出字段",
        "",
        *_render_output_table(node),
        "",
        "### 教师可读投影模板",
        "",
        *_render_projection(node),
        "",
    ]


def _render_chapter(
    filename: str, source: Mapping[str, Any], nodes_by_key: Mapping[str, Mapping[str, Any]]
) -> str:
    package = cast(Mapping[str, Any], source["package"])
    lines = generated_header(CHAPTER_TITLES[filename])
    lines.extend(
        [
            f"内容包：`{package['package_key']}@{package['semantic_version']}`。",
            "",
            "说明：Task 是教师在创作台可修改的业务指令；Role、Method 和 Quality Gate "
            "由平台固定，防止结构和教学边界被改坏。",
            "",
        ]
    )
    for position, key in enumerate(CHAPTER_NODE_KEYS[filename], start=1):
        lines.extend(_render_node(nodes_by_key[key], position))
    return "\n".join(lines).rstrip() + "\n"


def _render_readme(source: Mapping[str, Any]) -> str:
    package = cast(Mapping[str, Any], source["package"])
    lines = generated_header("内置生成提示词与模板说明")
    lines.extend(
        [
            "- **Owner：** 工作流与内容包维护者。",
            "- **Audience：** 产品负责人、内容管理员、后端/前端开发与测试人员。",
            "- **机器权威源：** `workflow/builtin/primary_math_courseware/generation-source.json` "
            "和黄金 Fixture；本目录不是第二套可手改事实。",
            "- **更新规则：** 修改权威源后运行渲染脚本；测试会逐字检查生成结果。",
            "- **替换/删除规则：** 内容包退役或生成方式变化时，由同一 PR 替换入口并删除本目录。",
            "",
            f"当前内容包：`{package['package_key']}@{package['semantic_version']}`，共 "
            f"{sum(len(keys) for keys in CHAPTER_NODE_KEYS.values())} 个模型节点。",
            "",
            "## 怎么看",
            "",
            "每个节点都按同一顺序说明：教师填写 → 系统自动带入 → 实际四层提示词 → "
            "结构化输出字段 → 教师可读投影模板。",
            "",
            "- **Task：** 教师可以在创作台修改的业务指令。",
            "- **Role / Method / Quality Gate：** 平台固定，教师不能用改 Prompt 的方式"
            "绕过结构和教学边界。",
            "- **Context：** 上游批准快照，不要求教师复制粘贴。",
            "- **输出字段：** 系统内部结构；教师看到的是投影后的教案、PPT 设计稿或视频生产包。",
            "",
            "## 分册",
            "",
            "1. [课时划分与十二部分教案](LESSON.md)",
            "2. [三类九套与最小课程锚定](INTRO.md)",
            "3. [PPT 内容分析、大纲与逐页设计](PPT_DESIGN.md)",
            "4. [PPT 封面与正文图片](PPT_IMAGES.md)",
            "5. [视频剧本、粗分镜与视觉母图](VIDEO_SCRIPT_AND_STYLE.md)",
            "6. [视频四类图片资产](VIDEO_ASSETS.md)",
            "7. [视频细分镜与逐镜头生成](VIDEO_SHOTS.md)",
            "8. [音频、TTS 与课堂质量验收](AUDIO_AND_QUALITY.md)",
            "9. [“1～5的认识”黄金测试示例](GOLDEN_CASE.md)",
            "",
            "## 重新生成与检查",
            "",
            "```powershell",
            "uv run python scripts\\render_builtin_generation_guide.py",
            "uv run python scripts\\render_builtin_generation_guide.py --check",
            "uv run pytest tests\\contract\\test_generation_guide.py -q",
            "```",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_chapter_documents(source: Mapping[str, Any]) -> dict[str, str]:
    nodes = cast(list[dict[str, Any]], source["nodes"])
    nodes_by_key = {cast(str, node["template_key"]): node for node in nodes}
    expected = {key for keys in CHAPTER_NODE_KEYS.values() for key in keys}
    if set(nodes_by_key) != expected:
        raise ValueError("chapter mapping must cover every generation node exactly once")
    documents = {"README.md": _render_readme(source)}
    for filename in CHAPTER_NODE_KEYS:
        documents[filename] = _render_chapter(filename, source, nodes_by_key)
    return documents
