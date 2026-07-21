"""Injectable deterministic text provider for node-output tests and CI."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from apps.api.model_gateway.contracts import (
    ModelUsage,
    TextModelRequest,
    TextProviderResult,
)


class DeterministicNodeOutputProvider:
    provider_name = "deterministic-node-fake"
    model_name = "node-output-v1"

    def __init__(self, output: Mapping[str, Any]) -> None:
        self._text = json.dumps(
            output,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        self.calls = 0

    async def complete(self, request: TextModelRequest) -> TextProviderResult:
        self.calls += 1
        return TextProviderResult(
            text=self._text,
            provider_request_id=f"fake:{request.request_id}",
            actual_model=self.model_name,
            finish_reason="stop",
            usage=ModelUsage(
                prompt_tokens=8,
                completion_tokens=4,
                total_tokens=12,
                cost=Decimal("0"),
            ),
        )
