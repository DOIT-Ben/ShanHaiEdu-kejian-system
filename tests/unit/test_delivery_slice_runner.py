from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.run_delivery_slice_tests import (
    _browser_report_passed,
    _resolved_executable_command,
    _run_backend,
    _run_browser,
)

BACKEND_SELECTOR = (
    "tests/integration/test_identity_session_api.py::"
    "test_current_session_returns_public_principal_and_csrf"
)
SELECTOR = "apps/web/e2e/real-api/session.spec.ts::restores session"


def _browser_report(
    specs: list[tuple[str, str]] | None = None,
    **stats: int,
) -> dict[str, object]:
    report_stats = {
        "expected": 1,
        "skipped": 0,
        "unexpected": 0,
        "flaky": 0,
        **stats,
    }
    return {
        "suites": [
            {
                "specs": [
                    {"file": file_name, "title": title}
                    for file_name, title in specs or [("session.spec.ts", "restores session")]
                ]
            }
        ],
        "stats": report_stats,
    }


def test_resolved_executable_command_keeps_native_binary() -> None:
    assert _resolved_executable_command("/usr/bin/pnpm", platform_name="posix") == ["/usr/bin/pnpm"]


def test_windows_batch_shim_uses_power_shell_script(tmp_path: Path, monkeypatch) -> None:
    batch_path = tmp_path / "pnpm.cmd"
    powershell_path = tmp_path / "pnpm.ps1"
    batch_path.touch()
    powershell_path.touch()
    monkeypatch.setattr("scripts.run_delivery_slice_tests.shutil.which", lambda name: "pwsh.exe")

    assert _resolved_executable_command(str(batch_path), platform_name="nt") == [
        "pwsh.exe",
        "-NoProfile",
        "-File",
        str(powershell_path),
    ]


def test_windows_batch_shim_without_power_shell_fails_closed(tmp_path: Path, monkeypatch) -> None:
    batch_path = tmp_path / "pnpm.cmd"
    batch_path.touch()
    monkeypatch.setattr("scripts.run_delivery_slice_tests.shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="PowerShell 7"):
        _resolved_executable_command(str(batch_path), platform_name="nt")


def test_run_backend_reports_subprocess_timeout(monkeypatch) -> None:
    def run_backend(*args, **kwargs):
        assert kwargs["timeout"] == 300
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr("scripts.run_delivery_slice_tests.subprocess.run", run_backend)

    with pytest.raises(RuntimeError) as error:
        _run_backend(BACKEND_SELECTOR)

    assert "backend" in str(error.value)
    assert BACKEND_SELECTOR in str(error.value)
    assert "300 seconds" in str(error.value)


def test_run_browser_reads_report_file_instead_of_stdout(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.run_delivery_slice_tests._playwright_command",
        lambda relative_path, title: ["playwright"],
    )

    def run_playwright(*args, **kwargs):
        report_path = Path(kwargs["env"]["PLAYWRIGHT_JSON_OUTPUT_FILE"])
        report_path.write_text(json.dumps(_browser_report()), encoding="utf-8")
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="non-JSON process output",
            stderr="",
        )

    monkeypatch.setattr("scripts.run_delivery_slice_tests.subprocess.run", run_playwright)

    _run_browser(SELECTOR)


def test_run_browser_rejects_missing_report_file(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.run_delivery_slice_tests._playwright_command",
        lambda relative_path, title: ["playwright"],
    )
    monkeypatch.setattr(
        "scripts.run_delivery_slice_tests.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    with pytest.raises(RuntimeError, match="did not create its JSON report"):
        _run_browser(SELECTOR)


def test_run_browser_reports_subprocess_timeout(monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.run_delivery_slice_tests._playwright_command",
        lambda relative_path, title: ["playwright"],
    )

    def run_playwright(*args, **kwargs):
        assert kwargs["timeout"] == 900
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr("scripts.run_delivery_slice_tests.subprocess.run", run_playwright)

    with pytest.raises(RuntimeError) as error:
        _run_browser(SELECTOR)

    assert "browser" in str(error.value)
    assert SELECTOR in str(error.value)
    assert "900 seconds" in str(error.value)


@pytest.mark.parametrize(
    "specs",
    [
        [("session.spec.ts", "restores session"), ("logout.spec.ts", "logs out")],
        [("wrong.spec.ts", "restores session")],
        [("session.spec.ts", "wrong title")],
    ],
)
def test_browser_report_rejects_multiple_or_wrong_specs(specs: list[tuple[str, str]]) -> None:
    assert not _browser_report_passed(
        _browser_report(specs),
        expected_file="session.spec.ts",
        expected_title="restores session",
    )


@pytest.mark.parametrize("outcome", ["skipped", "flaky"])
def test_browser_report_rejects_skipped_or_flaky(outcome: str) -> None:
    assert not _browser_report_passed(
        _browser_report(**{outcome: 1}),
        expected_file="session.spec.ts",
        expected_title="restores session",
    )
