from __future__ import annotations

import json

from apps.api.cli import run_model_smoke
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.settings import get_settings


async def test_fake_cli_summary_excludes_prompt_and_model_text(capsys) -> None:
    get_settings.cache_clear()
    try:
        exit_code = await run_model_smoke(
            capability=ModelCapability.TEXT_SMOKE,
            real=False,
        )
    finally:
        get_settings.cache_clear()

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["conclusion"] == "passed"
    assert "text" not in summary
    assert "prompt" not in summary
    assert "SHANHAIEDU_FAKE_SMOKE_OK" not in json.dumps(summary)
