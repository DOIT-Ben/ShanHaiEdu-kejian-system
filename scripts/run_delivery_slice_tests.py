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
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOT = ROOT / "contracts/delivery-slices"
MANIFEST_SCHEMA = ROOT / "contracts/delivery-slice.schema.json"
FAILED_PYTEST_OUTCOMES = re.compile(r"\b(?:skipped|xfailed|xpassed)\b")


def _selectors() -> tuple[list[str], list[str]]:
    backend: set[str] = set()
    browser: set[str] = set()
    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for path in sorted((*MANIFEST_ROOT.glob("*.yaml"), *MANIFEST_ROOT.glob("*.yml"))):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        schema_errors = sorted(
            validator.iter_errors(document),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
        if schema_errors:
            first_error = schema_errors[0]
            location = ".".join(str(part) for part in first_error.absolute_path) or "<root>"
            raise ValueError(
                f"invalid delivery manifest {path.relative_to(ROOT)} at "
                f"{location}: {first_error.message}"
            )
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


def _playwright_command(relative_path: str, title: str) -> list[str]:
    package_path = relative_path.removeprefix("apps/web/")
    pnpm = os.environ.get("PNPM_EXECUTABLE", "pnpm")
    return [
        pnpm,
        "--filter",
        "@shanhaiedu/web",
        "exec",
        "playwright",
        "test",
        "--config=playwright.real-api.config.ts",
        package_path,
        "--grep",
        f"{re.escape(title)}$",
        "--reporter=json",
    ]


def _reported_specs(report: object) -> list[tuple[str, str]]:
    if not isinstance(report, dict):
        return []
    found: list[tuple[str, str]] = []
    pending = list(report.get("suites", [])) if isinstance(report.get("suites"), list) else []
    while pending:
        suite = pending.pop()
        if not isinstance(suite, dict):
            continue
        if isinstance(suite.get("suites"), list):
            pending.extend(suite["suites"])
        for spec in suite.get("specs", []) if isinstance(suite.get("specs"), list) else []:
            if (
                isinstance(spec, dict)
                and isinstance(spec.get("file"), str)
                and isinstance(spec.get("title"), str)
            ):
                found.append((spec["file"], spec["title"]))
    return found


def _browser_report_passed(
    report: object,
    *,
    expected_file: str,
    expected_title: str,
) -> bool:
    if not isinstance(report, dict):
        return False
    stats = report.get("stats", {})
    if not isinstance(stats, dict):
        return False
    return (
        _reported_specs(report) == [(expected_file, expected_title)]
        and stats.get("expected", 0) >= 1
        and stats.get("skipped", 0) == 0
        and stats.get("unexpected", 0) == 0
        and stats.get("flaky", 0) == 0
    )


def _run_browser(selector: str) -> None:
    relative_path, separator, title = selector.partition("::")
    if not separator or not relative_path.startswith("apps/web/") or not title:
        raise ValueError(f"invalid Playwright selector: {selector}")
    result = subprocess.run(
        _playwright_command(relative_path, title),
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
    if result.returncode != 0 or not _browser_report_passed(
        report,
        expected_file=relative_path.removeprefix("apps/web/e2e/real-api/"),
        expected_title=title,
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
