#!/usr/bin/env python3
"""Validate an extracted ShanHaiEdu content package directory."""

from __future__ import annotations

import argparse
from pathlib import Path

from workflow.content_package import validate_content_package

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    args = parser.parse_args()
    package = validate_content_package(
        args.package_root,
        contracts_root=ROOT / "contracts",
    )
    print(
        f"validated {package.manifest['package_key']} "
        f"{package.manifest['semantic_version']} ({len(package.items)} items)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
