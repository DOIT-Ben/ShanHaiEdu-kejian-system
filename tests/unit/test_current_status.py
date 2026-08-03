from __future__ import annotations

import re
from pathlib import Path

from scripts.check_repository import FULLWIDTH_COLON, check_current_status

FULLWIDTH_SEMICOLON = "\N{FULLWIDTH SEMICOLON}"
ROOT = Path(__file__).resolve().parents[2]
REQUIRED_SECTIONS = f"""\
# 当前项目状态

当前阶段{FULLWIDTH_COLON}阶段0出口尚未关闭{FULLWIDTH_SEMICOLON}阶段1后端轨道接近出口

## 当前可演示成果

内容

## 已完成

内容

## 当前工作

内容

## 当前阻塞

内容

## 下一个阶段出口

内容

## 接手提示

内容
"""


def create_backend_baseline(root: Path) -> None:
    for relative in (
        "apps/api/main.py",
        "workers/main.py",
        "infra/compose.yaml",
        ".github/workflows/backend-quality.yml",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()


def section(text: str, heading: str) -> str:
    body = text.split(f"## {heading}\n", maxsplit=1)[1]
    return body.split("\n## ", maxsplit=1)[0]


def test_live_current_status_records_completed_public_acceptance_and_stage_five_gate() -> None:
    text = (ROOT / "CURRENT_STATUS.md").read_text(encoding="utf-8")

    completed = section(text, "已完成")
    current = section(text, "当前工作")
    blocked = section(text, "当前阻塞")
    next_exit = section(text, "下一个阶段出口")

    assert "Issue #244" in completed
    assert "PR #275" in completed
    assert "公网真实教师流" in completed
    assert "单Attempt成功事实" in completed
    assert "Issue #244" not in current
    assert "status:in-progress" not in text
    assert "阶段5 Decision Issue" in current
    assert "没有已获准实施的阶段5功能分支" in current
    assert "Issue #244" not in blocked
    assert "公网十二部分教案验收被" not in blocked
    assert "Issue #244" not in next_exit
    assert re.search(r"`main@[0-9a-f]{40}`", text)
    assert re.search(r"入口为`https://[^`]+`", text)
    assert "共享同一ECS" in blocked
    assert "Decision Issue" in next_exit
    assert "先写失败测试" in next_exit
    assert "独立reviewer" in next_exit
    assert "exact base/head" in next_exit

    for next_slice_candidate in (
        "PPT/PPTX",
        "完整图片链",
        "完整视频链",
        "TTS",
    ):
        assert next_slice_candidate in blocked
        assert next_slice_candidate in next_exit

    for stale_claim in (
        "仍未关闭",
        "尚无通过证据",
        "剩余公网十二部分教案",
        "被生产模型路由边界阻塞",
    ):
        assert stale_claim not in text


def test_current_status_accepts_controlled_stage_overlap(tmp_path: Path) -> None:
    create_backend_baseline(tmp_path)
    status = tmp_path / "CURRENT_STATUS.md"
    status.write_text(REQUIRED_SECTIONS, encoding="utf-8")
    errors: list[str] = []

    check_current_status(status, tmp_path, errors)

    assert errors == []


def test_current_status_requires_stage_one_backend_acknowledgement(tmp_path: Path) -> None:
    create_backend_baseline(tmp_path)
    status = tmp_path / "CURRENT_STATUS.md"
    status.write_text(
        REQUIRED_SECTIONS.replace(
            f"当前阶段{FULLWIDTH_COLON}阶段0出口尚未关闭{FULLWIDTH_SEMICOLON}阶段1后端轨道接近出口",
            f"当前阶段{FULLWIDTH_COLON}阶段0——协作与工程基线",
        ),
        encoding="utf-8",
    )
    errors: list[str] = []

    check_current_status(status, tmp_path, errors)

    assert errors == [
        "CURRENT_STATUS.md does not acknowledge the implemented stage 1 backend track"
    ]


def test_current_status_rejects_proven_stale_backend_claim(tmp_path: Path) -> None:
    create_backend_baseline(tmp_path)
    status = tmp_path / "CURRENT_STATUS.md"
    status.write_text(
        REQUIRED_SECTIONS.replace(
            "## 当前阻塞",
            "尚未初始化可运行的后端平台基座和CI。\n\n## 当前阻塞",
        ),
        encoding="utf-8",
    )
    errors: list[str] = []

    check_current_status(status, tmp_path, errors)

    assert errors == [
        "CURRENT_STATUS.md contains a stale backend claim: 尚未初始化可运行的后端平台基座和CI"
    ]


def test_current_status_requires_canonical_sections(tmp_path: Path) -> None:
    status = tmp_path / "CURRENT_STATUS.md"
    status.write_text(REQUIRED_SECTIONS.replace("## 当前阻塞\n", ""), encoding="utf-8")
    errors: list[str] = []

    check_current_status(status, tmp_path, errors)

    assert errors == ["CURRENT_STATUS.md missing required section: ## 当前阻塞"]
