from __future__ import annotations

from pathlib import Path

from scripts.check_repository import FULLWIDTH_COLON, check_current_status

FULLWIDTH_SEMICOLON = "\N{FULLWIDTH SEMICOLON}"
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
