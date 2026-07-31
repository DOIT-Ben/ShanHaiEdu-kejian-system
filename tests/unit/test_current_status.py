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


def test_live_current_status_records_post_mvp_convergence() -> None:
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
    assert "Issue #165" in current
    assert "第三次" in current
    assert "第四次" in current
    assert "status:blocked" in current
    assert "不自动重试" in blocked
    assert "Issue #233" in current
    assert "Issue #237" in current
    assert "status:ready" in current
    assert "Issue #233" not in next_exit
    assert "Issue #237" not in next_exit
    assert "Issue #244" in next_exit
    assert "status:blocked" in next_exit

    for required_decision in (
        "主机身份、所有权、操作系统和可用资源",
        "域名、DNS、TLS证书和反向代理",
        "Web、API、Worker、PostgreSQL、Redis、对象存储",
        "Session/CSRF/CORS/Cookie、访问码、Provider和对象存储密钥",
        "Alembic迁移、迁移前备份、恢复验证",
        "健康检查、结构化日志、错误率、延迟、队列深度、磁盘和数据库连接监控",
        "精确版本发布、回退触发条件、旧版本保留和回退演练",
        "受控内测或公开开放",
    ):
        assert required_decision in blocked


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
