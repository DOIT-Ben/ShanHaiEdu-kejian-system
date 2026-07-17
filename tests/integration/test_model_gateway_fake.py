from __future__ import annotations

import json

from apps.api.model_gateway.contracts import ModelCapability, TextModelRequest
from apps.api.model_gateway.fake import DeterministicFakeTextProvider
from apps.api.model_gateway.gateway import ModelGateway


async def test_fake_gateway_audit_excludes_prompt_and_response(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def capture(_message: str, *, extra: dict[str, object]) -> None:
        captured.update(extra)

    monkeypatch.setattr("apps.api.model_gateway.gateway.logger.info", capture)
    prompt = "private-smoke-prompt-marker"
    gateway = ModelGateway({ModelCapability.TEXT_SMOKE: DeterministicFakeTextProvider()})

    result = await gateway.generate_text(
        TextModelRequest(
            capability=ModelCapability.TEXT_SMOKE,
            request_id="req-audit-safe",
            prompt=prompt,
        )
    )

    assert result.text == "SHANHAIEDU_FAKE_SMOKE_OK"
    rendered = json.dumps(captured)
    assert prompt not in rendered
    assert result.text not in rendered
    assert captured["request_id"] == "req-audit-safe"
    assert captured["provider"] == "deterministic-fake"
