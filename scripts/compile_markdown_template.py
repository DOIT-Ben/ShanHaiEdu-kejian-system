#!/usr/bin/env python3
"""Compile a reviewed Markdown TemplateDraft into a validated content package."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, cast

from workflow.markdown_template_compiler import (
    MarkdownTemplateCompilationError,
    compile_markdown_template,
    write_compiled_content_package,
)

ROOT = Path(__file__).resolve().parents[1]
MAX_COMPILATION_INPUT_BYTES = 5_000_000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        draft = _load_object(args.draft)
        profile = _load_object(args.profile)
        compiled = compile_markdown_template(
            draft,
            profile,
            contracts_root=ROOT / "contracts",
        )
        write_compiled_content_package(compiled, args.output)
    except MarkdownTemplateCompilationError as exc:
        _write(2, f"{exc.code}: {exc}\n")
        return 2
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        _write(2, f"MARKDOWN_COMPILE_INPUT_INVALID: {exc}\n")
        return 2

    entrypoint = cast(list[str], compiled.manifest["entrypoints"])[0]
    _write(1, f"compiled {entrypoint} ({len(compiled.items)} items)\n")
    return 0


def _load_object(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        payload = stream.read(MAX_COMPILATION_INPUT_BYTES + 1)
    if len(payload) > MAX_COMPILATION_INPUT_BYTES:
        raise ValueError(f"JSON document exceeds size limit: {path.name}")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path.name}")
    return cast(dict[str, Any], value)


def _write(file_descriptor: int, value: str) -> None:
    os.write(file_descriptor, value.encode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
