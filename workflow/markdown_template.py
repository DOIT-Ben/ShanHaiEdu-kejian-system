"""Parse untrusted Markdown into an administrator-reviewable template draft."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, cast
from urllib.parse import urlparse

from markdown_it import MarkdownIt
from markdown_it.token import Token

MAX_MARKDOWN_BYTES = 2_000_000
ADAPTER_VERSION = "shanhai.markdown-template/v1"
UNSAFE_LINK_SCHEMES = frozenset({"data", "file", "javascript", "vbscript"})


class MarkdownTemplateError(ValueError):
    """Raised when Markdown cannot safely become a template draft."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class _Heading:
    level: int
    title: str
    start: int
    end: int


def parse_markdown_template(payload: bytes, *, source_name: str) -> dict[str, Any]:
    """Parse UTF-8 Markdown into a deterministic review draft."""

    source = _decode_source(payload)
    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    parser.validateLink = _accept_link_for_validation
    tokens = parser.parse(source)
    _validate_tokens(tokens)
    headings = _collect_headings(tokens)
    sections = [heading for heading in headings if heading.level == 2]
    if not sections:
        raise MarkdownTemplateError(
            "MARKDOWN_NO_SECTIONS",
            "Markdown must contain at least one level-two section",
        )

    lines = source.splitlines()
    warnings: list[dict[str, Any]] = []
    title, title_heading = _resolve_title(headings, source_name, warnings)
    preamble = _extract_preamble(lines, title_heading, sections[0])
    _warn_about_preamble(preamble, headings, sections[0], warnings)
    _warn_about_orphan_subsections(headings, sections[0], warnings)
    parsed_sections = _build_sections(lines, headings, sections, warnings)
    safe_name = _safe_source_name(source_name)
    return {
        "adapter_version": ADAPTER_VERSION,
        "state": "needs_review",
        "source": {
            "name": safe_name,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_length": len(payload),
        },
        "title": title,
        "preamble_markdown": preamble,
        "sections": parsed_sections,
        "warnings": warnings,
    }


def render_markdown_template(draft: Mapping[str, Any]) -> str:
    """Render the visible draft content as normalized Markdown."""

    chunks = [f"# {cast(str, draft['title'])}"]
    preamble = cast(str, draft["preamble_markdown"])
    if preamble:
        chunks.append(preamble)
    sections = cast(list[dict[str, Any]], draft["sections"])
    for section in sections:
        chunks.append(f"## {section['title']}")
        body = cast(str, section["body_markdown"])
        if body:
            chunks.append(body)
        for subsection in cast(list[dict[str, Any]], section["subsections"]):
            chunks.append(f"### {subsection['title']}")
            subsection_body = cast(str, subsection["body_markdown"])
            if subsection_body:
                chunks.append(subsection_body)
    return "\n\n".join(chunks).rstrip() + "\n"


def _decode_source(payload: bytes) -> str:
    if len(payload) > MAX_MARKDOWN_BYTES:
        raise MarkdownTemplateError(
            "MARKDOWN_TOO_LARGE",
            f"Markdown exceeds {MAX_MARKDOWN_BYTES} bytes",
        )
    try:
        source = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MarkdownTemplateError(
            "MARKDOWN_INVALID_UTF8",
            "Markdown must use UTF-8 encoding",
        ) from exc
    if not source.strip():
        raise MarkdownTemplateError("MARKDOWN_EMPTY", "Markdown cannot be empty")
    if "\x00" in source:
        raise MarkdownTemplateError(
            "MARKDOWN_UNSAFE_CONTROL",
            "Markdown contains an unsupported control character",
        )
    return source


def _validate_tokens(tokens: list[Token]) -> None:
    for token in _walk_tokens(tokens):
        if token.type in {"html_block", "html_inline"}:
            raise MarkdownTemplateError(
                "MARKDOWN_UNSAFE_HTML",
                "Raw HTML is not supported in Markdown templates",
            )
        if token.type == "image":
            raise MarkdownTemplateError(
                "MARKDOWN_UNSUPPORTED_IMAGE",
                "Images are outside the Markdown adapter V1 scope",
            )
        if token.type == "link_open":
            raw_href = token.attrGet("href")
            href = raw_href if isinstance(raw_href, str) else ""
            if urlparse(href).scheme.lower() in UNSAFE_LINK_SCHEMES:
                raise MarkdownTemplateError(
                    "MARKDOWN_UNSAFE_LINK",
                    "Markdown contains an unsafe link scheme",
                )


def _accept_link_for_validation(url: str) -> bool:
    return True


def _walk_tokens(tokens: list[Token]) -> Iterator[Token]:
    pending = list(reversed(tokens))
    while pending:
        token = pending.pop()
        yield token
        if token.children:
            pending.extend(reversed(token.children))


def _collect_headings(tokens: list[Token]) -> list[_Heading]:
    headings: list[_Heading] = []
    nesting_depth = 0
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.map is not None and nesting_depth == 0:
            inline = tokens[index + 1]
            title = _inline_text(inline).strip()
            if not title:
                raise MarkdownTemplateError(
                    "MARKDOWN_EMPTY_SECTION_TITLE",
                    f"Heading on line {token.map[0] + 1} cannot be empty",
                )
            headings.append(
                _Heading(
                    level=int(token.tag[1:]),
                    title=title,
                    start=token.map[0],
                    end=token.map[1],
                )
            )
        nesting_depth += token.nesting
    return headings


def _inline_text(token: Token) -> str:
    if not token.children:
        return token.content
    return "".join(
        child.content for child in token.children if child.type in {"text", "code_inline"}
    )


def _resolve_title(
    headings: list[_Heading],
    source_name: str,
    warnings: list[dict[str, Any]],
) -> tuple[str, _Heading | None]:
    title_headings = [heading for heading in headings if heading.level == 1]
    if not title_headings:
        warnings.append(
            {
                "code": "TITLE_FROM_FILENAME",
                "message": "Document title was derived from the source filename",
            }
        )
        return _filename_title(source_name), None
    if len(title_headings) > 1:
        warnings.append(
            {
                "code": "MULTIPLE_DOCUMENT_TITLES",
                "message": "Only the first level-one heading is used as the template title",
                "line": title_headings[1].start + 1,
            }
        )
    return title_headings[0].title, title_headings[0]


def _extract_preamble(
    lines: list[str],
    title: _Heading | None,
    first_section: _Heading,
) -> str:
    if title is None or title.start >= first_section.start:
        return _markdown_slice(lines, 0, first_section.start)
    before_title = _markdown_slice(lines, 0, title.start)
    after_title = _markdown_slice(lines, title.end, first_section.start)
    return "\n\n".join(part for part in (before_title, after_title) if part)


def _warn_about_preamble(
    preamble: str,
    headings: list[_Heading],
    first_section: _Heading,
    warnings: list[dict[str, Any]],
) -> None:
    if not preamble:
        return
    first_content_line = next(
        (heading.start + 1 for heading in headings if heading.start < first_section.start),
        1,
    )
    warnings.append(
        {
            "code": "CONTENT_BEFORE_FIRST_SECTION",
            "message": "Content before the first level-two section was preserved as preamble",
            "line": first_content_line,
        }
    )


def _warn_about_orphan_subsections(
    headings: list[_Heading],
    first_section: _Heading,
    warnings: list[dict[str, Any]],
) -> None:
    for heading in headings:
        if heading.level == 3 and heading.start < first_section.start:
            warnings.append(
                {
                    "code": "ORPHAN_SUBSECTION",
                    "message": "Level-three heading appears before the first section",
                    "line": heading.start + 1,
                }
            )


def _build_sections(
    lines: list[str],
    headings: list[_Heading],
    section_headings: list[_Heading],
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    used_keys: set[str] = set()
    for index, heading in enumerate(section_headings):
        end = section_headings[index + 1].start if index + 1 < len(section_headings) else len(lines)
        children = [
            child for child in headings if child.level == 3 and heading.end <= child.start < end
        ]
        base_key, role = _classify_section(heading.title, index)
        section_key = _unique_key(base_key, used_keys, heading, warnings)
        body_end = children[0].start if children else end
        sections.append(
            {
                "section_key": section_key,
                "title": heading.title,
                "role": role,
                "content_mode": "mixed",
                "required": True,
                "editable": True,
                "repeatable": role == "process",
                "visible": True,
                "body_markdown": _markdown_slice(lines, heading.end, body_end),
                "subsections": _build_subsections(lines, children, end, section_key),
                "source_range": {
                    "start_line": heading.start + 1,
                    "end_line": max(heading.start + 1, end),
                },
            }
        )
        if role == "custom":
            warnings.append(
                {
                    "code": "UNKNOWN_SECTION_ROLE",
                    "message": f"Section role requires administrator confirmation: {heading.title}",
                    "line": heading.start + 1,
                }
            )
    return sections


def _build_subsections(
    lines: list[str],
    headings: list[_Heading],
    section_end: int,
    section_key: str,
) -> list[dict[str, Any]]:
    subsections: list[dict[str, Any]] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start if index + 1 < len(headings) else section_end
        subsections.append(
            {
                "subsection_key": f"{section_key}.subsection-{index + 1:03d}",
                "title": heading.title,
                "body_markdown": _markdown_slice(lines, heading.end, end),
                "source_range": {
                    "start_line": heading.start + 1,
                    "end_line": max(heading.start + 1, end),
                },
            }
        )
    return subsections


def _classify_section(title: str, index: int) -> tuple[str, str]:
    normalized = re.sub(
        r"^[一二三四五六七八九十0-9]+[、.\uFF0E)\uFF09\s]+",
        "",
        title,
    ).strip()
    rules = (
        (("基本信息", "教材依据"), "overview", "overview"),
        (("教材分析",), "textbook-analysis", "analysis"),
        (("学情分析",), "learner-analysis", "analysis"),
        (("教学分析",), "analysis", "analysis"),
        (("教学目标",), "goals", "goals"),
        (("重难点", "重点与难点", "教学重点", "教学难点"), "focus-areas", "goals"),
        (("教学准备",), "preparation", "preparation"),
        (("教学过程",), "process", "process"),
        (("板书",), "board", "assessment"),
        (("评价", "作业"), "assessment", "assessment"),
        (("反思", "预案"), "contingency", "contingency"),
        (("三类九套", "导入方案"), "intro-options", "intro_options"),
    )
    for terms, key, role in rules:
        if any(term in normalized for term in terms):
            return key, role
    return f"section-{index + 1:03d}", "custom"


def _unique_key(
    base_key: str,
    used_keys: set[str],
    heading: _Heading,
    warnings: list[dict[str, Any]],
) -> str:
    if base_key not in used_keys:
        used_keys.add(base_key)
        return base_key
    suffix = 2
    while f"{base_key}-{suffix}" in used_keys:
        suffix += 1
    key = f"{base_key}-{suffix}"
    used_keys.add(key)
    warnings.append(
        {
            "code": "DUPLICATE_SECTION_KEY",
            "message": f"Duplicate semantic section key was renamed to {key}",
            "line": heading.start + 1,
        }
    )
    return key


def _markdown_slice(lines: list[str], start: int, end: int) -> str:
    selected = lines[start:end]
    while selected and not selected[0].strip():
        selected.pop(0)
    while selected and not selected[-1].strip():
        selected.pop()
    return "\n".join(selected)


def _safe_source_name(source_name: str) -> str:
    name = PurePosixPath(source_name.replace("\\", "/")).name.strip()
    return (name or "template.md")[:255]


def _filename_title(source_name: str) -> str:
    name = _safe_source_name(source_name)
    title = name.rsplit(".", 1)[0].strip()
    return title or "未命名模板"
