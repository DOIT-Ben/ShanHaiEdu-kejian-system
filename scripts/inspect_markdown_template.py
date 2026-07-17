#!/usr/bin/env python3
"""Inspect untrusted Markdown as a template draft or normalized preview."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from workflow.markdown_template import (
    MarkdownTemplateError,
    parse_markdown_template,
    render_markdown_template,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    try:
        payload = args.source.read_bytes()
        draft = parse_markdown_template(payload, source_name=args.source.name)
    except OSError as exc:
        _write(2, f"MARKDOWN_READ_FAILED: {exc}\n")
        return 2
    except MarkdownTemplateError as exc:
        _write(2, f"{exc.code}: {exc}\n")
        return 2

    if args.format == "markdown":
        _write(1, render_markdown_template(draft))
    else:
        _write(1, json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


def _write(file_descriptor: int, value: str) -> None:
    os.write(file_descriptor, value.encode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
