from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from workflow.markdown_template import (
    MAX_MARKDOWN_BYTES,
    MarkdownTemplateError,
    parse_markdown_template,
    render_markdown_template,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
FIXTURE = CONTRACTS / "fixtures/markdown-template/math-comic-lesson.md"
CLI = ROOT / "scripts/inspect_markdown_template.py"


def load_schema() -> dict[str, Any]:
    value = json.loads(
        (CONTRACTS / "markdown-template-draft.schema.json").read_text(encoding="utf-8")
    )
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def visible_signature(draft: dict[str, Any]) -> object:
    return (
        draft["title"],
        draft["preamble_markdown"],
        [
            (
                section["title"],
                section["body_markdown"],
                [
                    (subsection["title"], subsection["body_markdown"])
                    for subsection in section["subsections"]
                ],
            )
            for section in draft["sections"]
        ],
    )


def assert_error(payload: bytes, code: str, *, source_name: str = "template.md") -> None:
    with pytest.raises(MarkdownTemplateError) as caught:
        parse_markdown_template(payload, source_name=source_name)
    assert caught.value.code == code


def test_math_comic_fixture_builds_schema_valid_eight_section_draft() -> None:
    draft = parse_markdown_template(FIXTURE.read_bytes(), source_name=FIXTURE.name)

    Draft202012Validator.check_schema(load_schema())
    cast(Any, Draft202012Validator(load_schema())).validate(draft)
    assert draft["adapter_version"] == "shanhai.markdown-template/v1"
    assert draft["state"] == "needs_review"
    assert draft["title"] == "《数学连环画》详细教案"
    assert len(draft["sections"]) == 8
    assert [section["role"] for section in draft["sections"]] == [
        "overview",
        "analysis",
        "goals",
        "goals",
        "preparation",
        "process",
        "assessment",
        "contingency",
    ]
    process = draft["sections"][5]
    assert process["repeatable"] is True
    assert [item["title"] for item in process["subsections"]] == [
        "激趣引入\uff088分钟\uff09",
        "核心探究\uff0820分钟\uff09",
        "应用与收束\uff0817分钟\uff09",
    ]


def test_parser_preserves_lists_quotes_tables_and_nested_headings() -> None:
    source = (
        b"# Demo\n\nIntro.\n\n## Section\n\n- one\n- two\n\n"
        b"| A | B |\n| - | - |\n| 1 | 2 |\n\n"
        b"### Child\n\n> note\n\n#### Detail\n\nText.\n"
    )

    draft = parse_markdown_template(source, source_name="demo.md")

    assert draft["preamble_markdown"] == "Intro."
    assert "- one\n- two" in draft["sections"][0]["body_markdown"]
    assert "| A | B |" in draft["sections"][0]["body_markdown"]
    assert draft["sections"][0]["subsections"][0]["body_markdown"] == (
        "> note\n\n#### Detail\n\nText."
    )


def test_missing_title_uses_filename_and_requires_review() -> None:
    draft = parse_markdown_template(
        "## 教学目标\n\n目标正文。\n".encode(),
        source_name="我的教案.md",
    )

    assert draft["title"] == "我的教案"
    assert draft["state"] == "needs_review"
    assert draft["warnings"][0]["code"] == "TITLE_FROM_FILENAME"


def test_unknown_and_duplicate_sections_get_deterministic_keys() -> None:
    source = """# Demo

## 自定义栏目

A

## 自定义栏目

B
""".encode()

    first = parse_markdown_template(source, source_name="demo.md")
    second = parse_markdown_template(source, source_name="demo.md")

    assert [section["section_key"] for section in first["sections"]] == [
        "section-001",
        "section-002",
    ]
    assert first == second
    assert {warning["code"] for warning in first["warnings"]} == {"UNKNOWN_SECTION_ROLE"}


def test_duplicate_semantic_sections_are_disambiguated() -> None:
    source = """# Demo

## 教学目标

A

## 教学目标

B
""".encode()

    draft = parse_markdown_template(source, source_name="demo.md")

    assert [section["section_key"] for section in draft["sections"]] == [
        "goals",
        "goals-2",
    ]
    assert [warning["code"] for warning in draft["warnings"]] == ["DUPLICATE_SECTION_KEY"]


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"", "MARKDOWN_EMPTY"),
        (b"# Title\n\nNo sections.\n", "MARKDOWN_NO_SECTIONS"),
        (b"# Title\n\n## Section\n\n<script>alert(1)</script>\n", "MARKDOWN_UNSAFE_HTML"),
        (b"# Title\n\n## Section\n\n![alt](image.png)\n", "MARKDOWN_UNSUPPORTED_IMAGE"),
        (b"# Title\n\n## Section\n\n[x](javascript:alert(1))\n", "MARKDOWN_UNSAFE_LINK"),
        (b"\xff\xfe", "MARKDOWN_INVALID_UTF8"),
    ],
)
def test_invalid_or_unsafe_markdown_is_rejected(payload: bytes, code: str) -> None:
    assert_error(payload, code)


def test_oversized_markdown_is_rejected() -> None:
    assert_error(b"x" * (MAX_MARKDOWN_BYTES + 1), "MARKDOWN_TOO_LARGE")


def test_normalized_markdown_is_deterministic_and_round_trips_visible_content() -> None:
    draft = parse_markdown_template(FIXTURE.read_bytes(), source_name=FIXTURE.name)

    first = render_markdown_template(draft)
    second = render_markdown_template(draft)
    reparsed = parse_markdown_template(first.encode(), source_name="normalized.md")

    assert first == second
    assert first.endswith("\n")
    assert visible_signature(reparsed) == visible_signature(draft)


def test_draft_exposes_business_settings_without_schema_authoring() -> None:
    draft = parse_markdown_template(FIXTURE.read_bytes(), source_name=FIXTURE.name)

    for section in draft["sections"]:
        assert section["content_mode"] == "mixed"
        assert section["required"] is True
        assert section["editable"] is True
        assert section["visible"] is True


@pytest.mark.parametrize("output_format", ["json", "markdown"])
def test_cli_emits_requested_draft_projection(output_format: str) -> None:
    result = subprocess.run(
        [sys.executable, str(CLI), str(FIXTURE), "--format", output_format],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    if output_format == "json":
        validator = Draft202012Validator(load_schema())
        cast(Any, validator).validate(json.loads(result.stdout))
    else:
        assert result.stdout.startswith("# 《数学连环画》详细教案\n")


def test_cli_reports_stable_error_code(tmp_path: Path) -> None:
    unsafe = tmp_path / "unsafe.md"
    unsafe.write_text("# Demo\n\n## Section\n\n<script>x</script>\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(CLI), str(unsafe)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 2
    assert result.stderr.startswith("MARKDOWN_UNSAFE_HTML:")
