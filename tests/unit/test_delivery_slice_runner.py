from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_delivery_slice_tests as runner


def _report(
    *,
    file: str = "harness.spec.ts",
    title: str = "proves the real boundary",
    expected: int = 1,
    skipped: int = 0,
    unexpected: int = 0,
    flaky: int = 0,
) -> dict[str, object]:
    return {
        "suites": [
            {
                "title": "harness.spec.ts",
                "specs": [{"file": file, "title": title}],
            }
        ],
        "stats": {
            "expected": expected,
            "skipped": skipped,
            "unexpected": unexpected,
            "flaky": flaky,
        },
    }


def test_playwright_command_matches_full_title_suffix_not_bare_full_path() -> None:
    command = runner._playwright_command(
        "apps/web/e2e/real-api/harness.spec.ts",
        "proves the real boundary",
    )

    grep = command[command.index("--grep") + 1]
    assert grep == "proves\\ the\\ real\\ boundary$"
    assert not grep.startswith("^")


def test_browser_report_requires_exact_selected_spec_and_clean_result() -> None:
    expected = {
        "expected_file": "harness.spec.ts",
        "expected_title": "proves the real boundary",
    }

    assert runner._browser_report_passed(_report(), **expected)
    assert not runner._browser_report_passed({"suites": [], "stats": {}}, **expected)
    assert not runner._browser_report_passed(
        _report(title="different title"),
        **expected,
    )
    assert not runner._browser_report_passed(
        {
            **_report(),
            "suites": [
                *_report()["suites"],
                {
                    "title": "other.spec.ts",
                    "specs": [{"file": "other.spec.ts", "title": "another test"}],
                },
            ],
        },
        **expected,
    )
    assert not runner._browser_report_passed(_report(skipped=1), **expected)
    assert not runner._browser_report_passed(_report(unexpected=1), **expected)
    assert not runner._browser_report_passed(_report(flaky=1), **expected)


def test_selectors_reject_manifest_outside_json_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_root = tmp_path / "contracts/delivery-slices"
    manifest_root.mkdir(parents=True)
    schema_path = tmp_path / "contracts/delivery-slice.schema.json"
    schema_path.write_text(
        (Path(__file__).resolve().parents[2] / "contracts/delivery-slice.schema.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    (manifest_root / "211-invalid.yaml").write_text(
        "schema_version: 1\n"
        "issue: 211\n"
        "unexpected: true\n"
        "rows:\n"
        "  - page_route: /app/projects\n"
        "    navigation_path: /app/projects\n"
        "    api_requests:\n"
        "      - operation_id: listProjects\n"
        "        method: GET\n"
        "        path: /projects\n"
        "    formal_facts: [Project]\n"
        "    backend_tests: [tests/integration/test.py::test_project]\n"
        "    real_api_playwright: [apps/web/e2e/real-api/test.spec.ts::project]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "MANIFEST_ROOT", manifest_root)
    monkeypatch.setattr(runner, "MANIFEST_SCHEMA", schema_path)

    with pytest.raises(ValueError, match="invalid delivery manifest"):
        runner._selectors()


def test_report_parser_rejects_non_json_shape() -> None:
    assert runner._reported_specs(None) == []
    assert runner._reported_specs([]) == []
    assert runner._reported_specs(json.loads("{}")) == []
