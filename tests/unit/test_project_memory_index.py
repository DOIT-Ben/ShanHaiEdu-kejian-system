from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_repository import check_project_memory_index

VALID_INDEX = """\
# 项目记忆与接手索引

## 职责和权威

内容。

## 接手读取顺序

内容。

## 稳定产品原则

内容。

## 模块与事实入口

内容。

## 验证入口

内容。

## 记忆边界

内容。

## 维护责任

内容。
"""
WINDOWS_ABSOLUTE_PATH = "E" + ":" + r"\workspace\ShanHaiEdu"


def validate(tmp_path: Path, text: str) -> list[str]:
    index = tmp_path / "项目记忆与接手索引.md"
    index.write_text(text, encoding="utf-8")
    errors: list[str] = []
    check_project_memory_index(index, errors)
    return errors


def test_project_memory_index_accepts_routing_only_content(tmp_path: Path) -> None:
    assert validate(tmp_path, VALID_INDEX) == []


def test_project_memory_index_requires_canonical_sections(tmp_path: Path) -> None:
    errors = validate(
        tmp_path,
        VALID_INDEX.replace("## 记忆边界\n\n内容。\n\n", ""),
    )

    assert errors == ["project memory index missing required section: ## 记忆边界"]


@pytest.mark.parametrize(
    ("ephemeral", "expected"),
    (
        (f"本机入口: {WINDOWS_ABSOLUTE_PATH}", "local absolute path"),
        (
            "版本指纹: 0123456789abcdef0123456789abcdef01234567",
            "full commit SHA",
        ),
        ("当前分支: feat/123-live", "concrete branch state"),
        ("当前提交: 0c636a8", "concrete commit state"),
        ("当前 PR: #93", "concrete pull request state"),
        ("当前端口: 8000", "concrete port state"),
    ),
)
def test_project_memory_index_rejects_ephemeral_state(
    tmp_path: Path,
    ephemeral: str,
    expected: str,
) -> None:
    errors = validate(tmp_path, VALID_INDEX + f"\n{ephemeral}\n")

    assert errors == [f"project memory index contains {expected}"]
