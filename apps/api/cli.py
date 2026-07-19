"""Explicit administrative CLI entry points."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime

from apps.api.ids import new_uuid7
from apps.api.logging import configure_logging
from apps.api.model_gateway.contracts import (
    ModelCapability,
    ModelGatewayError,
    TextModelRequest,
)
from apps.api.model_gateway.factory import build_real_text_gateway
from apps.api.model_gateway.fake import DeterministicFakeTextProvider
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.settings import get_settings

TEXT_SMOKE_CAPABILITIES = (ModelCapability.TEXT_SMOKE,)


async def run_model_smoke(*, capability: ModelCapability, real: bool) -> int:
    settings = get_settings()
    configure_logging(
        service="shanhaiedu-model-smoke",
        environment=settings.environment,
        level=settings.log_level,
    )
    provider = None
    if real:
        try:
            gateway, provider = build_real_text_gateway(settings)
        except ModelGatewayError as error:
            print(_error_summary(error, capability, None, None))
            return 1
    else:
        fake = DeterministicFakeTextProvider()
        gateway = ModelGateway({ModelCapability.TEXT_SMOKE: fake})

    request_id = f"req_model_smoke_{new_uuid7()}"
    try:
        result = await gateway.generate_text(
            TextModelRequest(
                capability=capability,
                request_id=request_id,
                prompt="Reply with one short confirmation token for a connectivity smoke test.",
                max_output_tokens=128,
                temperature=0,
            )
        )
    except ModelGatewayError as error:
        print(
            _error_summary(
                error,
                capability,
                settings.text_provider_name,
                settings.text_provider_model,
                request_id=request_id,
            )
        )
        return 1
    finally:
        if provider is not None:
            await provider.aclose()

    print(
        json.dumps(
            {
                "conclusion": "passed",
                "utc": datetime.now(UTC).isoformat(),
                "capability": capability.value,
                "provider": result.route.provider,
                "configured_model": result.route.model,
                "actual_model": result.actual_model,
                "request_id": result.request_id,
                "provider_request_id": result.provider_request_id,
                "latency_ms": result.latency_ms,
                "usage": result.usage.model_dump(mode="json"),
            },
            ensure_ascii=True,
        )
    )
    return 0


def _error_summary(
    error: ModelGatewayError,
    capability: ModelCapability,
    provider: str | None,
    model: str | None,
    *,
    request_id: str | None = None,
) -> str:
    return json.dumps(
        {
            "conclusion": "failed",
            "utc": datetime.now(UTC).isoformat(),
            "capability": capability.value,
            "provider": provider,
            "configured_model": model,
            "request_id": request_id,
            "error_code": error.code.value,
            "retryable": error.retryable,
        },
        ensure_ascii=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ShanHaiEdu administrative commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    smoke = subparsers.add_parser("model-smoke", help="run an explicit text model smoke")
    smoke.add_argument(
        "--capability",
        choices=[capability.value for capability in TEXT_SMOKE_CAPABILITIES],
        required=True,
    )
    smoke.add_argument("--real", action="store_true")
    args = parser.parse_args()
    if args.command == "model-smoke":
        return asyncio.run(
            run_model_smoke(
                capability=ModelCapability(args.capability),
                real=bool(args.real),
            )
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
