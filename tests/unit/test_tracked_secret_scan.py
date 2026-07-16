from __future__ import annotations

from scripts.check_tracked_secrets import scan_text


def test_secret_scan_reports_key_without_exposing_value() -> None:
    fake_key = "sk-" + "test_" + "abcdefghijklmnopqrstuvwxyz"
    findings = scan_text(__file__, f'API_KEY="{fake_key}"')

    assert findings == [(1, "openai_style_key"), (1, "quoted_secret")]


def test_secret_scan_allows_explicit_local_examples() -> None:
    findings = scan_text(__file__, "PASSWORD=shanhai-local-only")

    assert findings == []
