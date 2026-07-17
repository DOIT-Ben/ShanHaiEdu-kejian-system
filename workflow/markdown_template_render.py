"""Render administrator-approved Markdown template draft projections."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast


def render_markdown_template(draft: Mapping[str, Any]) -> str:
    """Render the visible draft content as normalized Markdown."""

    chunks = [f"# {cast(str, draft['title'])}"]
    preamble = cast(str, draft["preamble_markdown"])
    if preamble:
        chunks.append(preamble)
    sections = cast(list[dict[str, Any]], draft["sections"])
    for section in sections:
        if not cast(bool, section["visible"]):
            continue
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
