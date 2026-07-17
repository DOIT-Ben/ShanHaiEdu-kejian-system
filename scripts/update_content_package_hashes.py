#!/usr/bin/env python3
"""Update semantic item hashes in a content package manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from workflow.content_package import (
    canonical_json_sha256,
    resolve_content_package_item_path,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    args = parser.parse_args()
    package_root = args.package_root.resolve()
    manifest_path = package_root / "manifest.json"
    manifest = _load_object(manifest_path)
    entries = cast(list[dict[str, Any]], manifest["items"])
    for entry in entries:
        item_path = resolve_content_package_item_path(
            package_root,
            cast(str, entry["path"]),
        )
        item = _load_object(item_path)
        entry["sha256"] = canonical_json_sha256(item)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return cast(dict[str, Any], value)


if __name__ == "__main__":
    raise SystemExit(main())
