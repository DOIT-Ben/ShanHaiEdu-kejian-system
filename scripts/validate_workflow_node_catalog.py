#!/usr/bin/env python3
"""Validate a declarative workflow node generation binding catalog."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from workflow.node_generation_binding import (
    NodeGenerationBindingError,
    load_workflow_node_catalog,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog_path", type=Path)
    args = parser.parse_args()
    try:
        validated = load_workflow_node_catalog(
            args.catalog_path,
            schema_path=ROOT / "contracts/workflow-node-generation-binding.schema.json",
        )
    except NodeGenerationBindingError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2
    print(
        f"validated {validated.catalog['catalog_key']} "
        f"{validated.catalog['semantic_version']} "
        f"({len(validated.catalog['nodes'])} nodes) sha256={validated.content_hash}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
