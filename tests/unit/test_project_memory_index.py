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
UNC_ABSOLUTE_PATH = "\\" * 2 + r"server\share\ShanHaiEdu"
POSIX_ABSOLUTE_PATH = "/" + "home/example/ShanHaiEdu"
GENERIC_POLICY_TEXT = """\

- **Branch**: 按 Issue 创建短分支
- `Commit`: 不在长期文档中记录
- PR: 只在 GitHub 实时查看
- Port: 使用当前进程核验
"""


def validate(tmp_path: Path, text: str) -> list[str]:
    index = tmp_path / "项目记忆与接手索引.md"
    index.write_text(text, encoding="utf-8")
    errors: list[str] = []
    check_project_memory_index(index, errors)
    return errors


def test_project_memory_index_accepts_routing_only_content(tmp_path: Path) -> None:
    assert validate(tmp_path, VALID_INDEX + GENERIC_POLICY_TEXT) == []


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
        (f"共享入口: {UNC_ABSOLUTE_PATH}", "local absolute path"),
        (f"服务端入口: {POSIX_ABSOLUTE_PATH}", "local absolute path"),
        (
            "版本指纹: 0123456789abcdef0123456789abcdef01234567",
            "full commit SHA",
        ),
        ("- **当前分支**: feat/123-live", "concrete branch state"),
        ("当前提交: 0c636a8", "concrete commit state"),
        ("当前 PR: #93", "concrete pull request state"),
        ("PR #95 已进入 review", "concrete pull request state"),
        ("当前端口: 8000", "concrete port state"),
        ("服务地址: http://127.0.0.1:8000", "concrete port state"),
    ),
)
def test_project_memory_index_rejects_ephemeral_state(
    tmp_path: Path,
    ephemeral: str,
    expected: str,
) -> None:
    errors = validate(tmp_path, VALID_INDEX + f"\n{ephemeral}\n")

    assert errors == [f"project memory index contains {expected}"]
