"""Render the built-in generation contracts as a deterministic Chinese guide."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from scripts.generation_guide_renderer import (
    CHAPTER_NODE_KEYS as CHAPTER_NODE_KEYS,
)
from scripts.generation_guide_renderer import (
    build_chapter_documents,
)
from scripts.golden_case_guide_renderer import render_golden_case

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "workflow/builtin/primary_math_courseware/generation-source.json"
DEFAULT_GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"
DEFAULT_OUTPUT = ROOT / "docs/workflows/generation-guide"


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return cast(dict[str, Any], value)


def _build_documents(source: Mapping[str, Any], golden: Mapping[str, Any]) -> dict[str, str]:
    documents = build_chapter_documents(source)
    documents["GOLDEN_CASE.md"] = render_golden_case(golden)
    return documents


def render_generation_guide(source_path: Path, golden_path: Path, output_root: Path) -> None:
    documents = _build_documents(_load_object(source_path), _load_object(golden_path))
    output_root.mkdir(parents=True, exist_ok=True)
    for filename, content in documents.items():
        (output_root / filename).write_text(content, encoding="utf-8", newline="\n")


def _check_generation_guide(source_path: Path, golden_path: Path, output_root: Path) -> None:
    documents = _build_documents(_load_object(source_path), _load_object(golden_path))
    actual_files = {path.name for path in output_root.glob("*.md")}
    if actual_files != set(documents):
        raise ValueError("generated guide file set is stale")
    for filename, expected in documents.items():
        if (output_root / filename).read_text(encoding="utf-8") != expected:
            raise ValueError(f"generated guide is stale: {filename}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--golden-case", type=Path, default=DEFAULT_GOLDEN_CASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        _check_generation_guide(args.source, args.golden_case, args.output)
        print(f"PASS: generation guide matches {args.source}")
    else:
        render_generation_guide(args.source, args.golden_case, args.output)
        print(f"rendered {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
