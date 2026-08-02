from __future__ import annotations

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


def test_live_current_status_records_production_mvp_closeout() -> None:
    text = (ROOT / "CURRENT_STATUS.md").read_text(encoding="utf-8")

    completed = section(text, "已完成")
    current = section(text, "当前工作")
    blocked = section(text, "当前阻塞")
    next_exit = section(text, "下一个阶段出口")

    assert "Issue #248" in completed
    assert "PR #252" in completed
    assert "Issue #248" not in current
    assert "PR #222与#230均已关闭" in completed
    assert "#222" not in current
    assert "#230" not in current
    assert "Issue #244" in completed
    assert "PR #254" in completed
    assert "#268" in completed
    assert "Issue #244" not in current
    assert "Issue #244" not in next_exit
    assert "8ec831072c643c7bc9b4cdcf2d240fd3f469bedd" in text
    assert "https://121.40.117.240" in text
    assert "3/3" in text
    assert "Issue #165" in current
    assert "status:blocked" in current
    assert "Issue #233" in current
    assert "Issue #237" in current
    assert "status:ready" in current
    assert "Issue #233" not in next_exit
    assert "Issue #237" not in next_exit
    assert "当前没有已批准且处于`status:in-progress`的产品实现Issue" in current
    assert "共享同一ECS" in blocked
    assert "阶段5产品方向尚未决定" in blocked
    assert "Decision Issue" in next_exit
    assert "先写失败测试" in next_exit
    assert "独立reviewer绑定final exact base/head" in next_exit
    assert "开放 Draft PR #254" not in text
    assert "hotfix/244-loopback-ingress-network" not in text

    for next_slice_candidate in (
        "PPT/PPTX",
        "完整图片链",
        "完整视频链",
        "TTS",
    ):
        assert next_slice_candidate in blocked
        assert next_slice_candidate in next_exit


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
