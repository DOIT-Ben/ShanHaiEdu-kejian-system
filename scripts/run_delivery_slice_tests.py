#!/usr/bin/env python3
"""Run every test selector declared by current vertical delivery manifests."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOT = ROOT / "contracts/delivery-slices"
FAILED_PYTEST_OUTCOMES = re.compile(r"\b(?:skipped|xfailed|xpassed)\b")


def _selectors() -> tuple[list[str], list[str]]:
    backend: set[str] = set()
    browser: set[str] = set()
    for path in sorted((*MANIFEST_ROOT.glob("*.yaml"), *MANIFEST_ROOT.glob("*.yml"))):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(document.get("rows"), list):
            raise ValueError(f"invalid delivery manifest: {path.relative_to(ROOT)}")
        for row in document["rows"]:
            if not isinstance(row, dict):
                raise ValueError(f"invalid delivery manifest row: {path.relative_to(ROOT)}")
            backend.update(row.get("backend_tests", []))
            browser.update(row.get("real_api_playwright", []))
    return sorted(backend), sorted(browser)


def _run_backend(selector: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", selector, "-q", "-rA"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = f"{result.stdout}\n{result.stderr}"
    if (
        result.returncode != 0
        or re.search(r"\b\d+\s+passed\b", output) is None
        or FAILED_PYTEST_OUTCOMES.search(output)
    ):
        raise RuntimeError(f"backend selector did not pass cleanly: {selector}\n{output}")


def _run_browser(selector: str) -> None:
    relative_path, separator, title = selector.partition("::")
    if not separator or not relative_path.startswith("apps/web/") or not title:
        raise ValueError(f"invalid Playwright selector: {selector}")
    package_path = relative_path.removeprefix("apps/web/")
    pnpm = os.environ.get("PNPM_EXECUTABLE", "pnpm")
    result = subprocess.run(
        [
            pnpm,
            "--filter",
            "@shanhaiedu/web",
            "exec",
            "playwright",
            "test",
            "--config=playwright.real-api.config.ts",
            package_path,
            "--grep",
            f"^{re.escape(title)}$",
            "--reporter=json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Playwright selector did not return JSON: {selector}\n{result.stdout}\n{result.stderr}"
        ) from error
    stats = report.get("stats", {}) if isinstance(report, dict) else {}
    if (
        result.returncode != 0
        or stats.get("expected", 0) < 1
        or stats.get("skipped", 0) != 0
        or stats.get("unexpected", 0) != 0
        or stats.get("flaky", 0) != 0
    ):
        raise RuntimeError(
            f"Playwright selector did not pass cleanly: {selector}\n"
            f"{result.stdout}\n{result.stderr}"
        )


def main() -> int:
    backend, browser = _selectors()
    for selector in backend:
        _run_backend(selector)
    for selector in browser:
        _run_browser(selector)
    print(
        f"delivery slice selectors passed: {len(backend)} backend, {len(browser)} real API browser"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
