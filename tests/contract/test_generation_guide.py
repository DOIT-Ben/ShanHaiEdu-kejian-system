# ruff: noqa: RUF001
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from scripts.golden_case_guide_renderer import render_golden_case
from scripts.render_builtin_generation_guide import (
    CHAPTER_NODE_KEYS,
    render_generation_guide,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "workflow/builtin/primary_math_courseware/generation-source.json"
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"
GUIDE = ROOT / "docs/workflows/generation-guide"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_generation_guide_is_reproducible(tmp_path: Path) -> None:
    generated = tmp_path / "generation-guide"
    render_generation_guide(SOURCE, GOLDEN_CASE, generated)

    generated_files = sorted(path.relative_to(generated) for path in generated.glob("*.md"))
    tracked_files = sorted(path.relative_to(GUIDE) for path in GUIDE.glob("*.md"))
    assert generated_files == tracked_files
    for relative in generated_files:
        assert (generated / relative).read_bytes() == (GUIDE / relative).read_bytes()


def test_generation_guide_covers_all_model_nodes_once() -> None:
    source = load_json(SOURCE)
    source_keys = {node["template_key"] for node in source["nodes"]}
    chapter_keys = [key for keys in CHAPTER_NODE_KEYS.values() for key in keys]

    assert len(source_keys) == 22
    assert set(chapter_keys) == source_keys
    assert len(chapter_keys) == len(set(chapter_keys))

    chapter_text = "\n".join(
        (GUIDE / name).read_text(encoding="utf-8") for name in CHAPTER_NODE_KEYS
    )
    for key in source_keys:
        assert chapter_text.count(f"(`{key}`)") == 1


def test_generation_guide_is_bounded_and_contains_readable_golden_case() -> None:
    expected_files = {
        "README.md",
        "LESSON.md",
        "INTRO.md",
        "PPT_DESIGN.md",
        "PPT_IMAGES.md",
        "VIDEO_SCRIPT_AND_STYLE.md",
        "VIDEO_ASSETS.md",
        "VIDEO_SHOTS.md",
        "AUDIO_AND_QUALITY.md",
        "GOLDEN_CASE.md",
    }
    assert {path.name for path in GUIDE.glob("*.md")} == expected_files

    for path in GUIDE.glob("*.md"):
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 300, path.name

    golden_text = (GUIDE / "GOLDEN_CASE.md").read_text(encoding="utf-8")
    assert "1～5的认识" in golden_text
    assert "物理页 3～5" in golden_text
    assert "三类九套" in golden_text
    assert "10 页 PPT" in golden_text
    assert "90 秒视频" in golden_text
    assert "本Fixture只证明合同、上下文和结构可独立启动" in golden_text
    assert "尚未授课，保留反思问题，待教师课后填写" in golden_text
    assert "封面 (`cover`)" in golden_text
    assert "not_taught" not in golden_text


def test_golden_case_guide_projects_machine_fields_without_stale_copies() -> None:
    golden = copy.deepcopy(load_json(GOLDEN_CASE))
    golden["source"]["pdf_page_indexes"] = [7, 9]
    golden["source"]["printed_pages"] = [21, 23]
    golden["source"]["verification"]["raw_source_committed"] = True
    golden["ppt"]["style_contract"]["body_background_mode"] = "patterned_test"
    golden["ppt"]["style_contract"]["image_rules"] = ["仅测试机器字段投影"]
    golden["video"]["asset_inventory"]["categories"]["creature"] = ["ASSET-CREATURE-TEST"]
    golden["delivery_expectations"]["golden_fixture_claim"] = "变异后的交付声明。"

    rendered = render_golden_case(golden)

    assert "物理页 7、9，对应印刷页 21、23" in rendered
    assert "原教材已提交仓库：是" in rendered
    assert "`patterned_test`" in rendered
    assert "仅测试机器字段投影" in rendered
    assert "本例没有生物类" not in rendered
    assert "变异后的交付声明" in rendered
    assert "`deterministic_fake_only`" in rendered
    assert "`real_text_image_video_smoke_tts_deferred`" in rendered


def test_golden_case_guide_rejects_unknown_provider_policy() -> None:
    golden = copy.deepcopy(load_json(GOLDEN_CASE))
    golden["delivery_expectations"]["ordinary_ci_provider_policy"] = "unsupported"

    with pytest.raises(ValueError, match="unsupported golden Provider policy"):
        render_golden_case(golden)
