from __future__ import annotations

from dataclasses import asdict
from uuid import UUID

import httpx
from pydantic import SecretStr

from apps.api.model_gateway.audit import (
    AttemptCompletion,
    AttemptHeartbeat,
    AttemptLease,
    AttemptRequestAudit,
    AttemptSuccessAudit,
)
from apps.api.model_gateway.contracts import (
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    TextModelRequest,
)
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.model_gateway.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleTextProvider,
)


class RecordingAuditSink:
    attempt_id = UUID("01980000-0000-7000-8000-000000000001")

    def __init__(self) -> None:
        self.events: list[object] = []

    def start(
        self,
        context: ModelAuditContext,
        request: AttemptRequestAudit,
        *,
        provider_name: str | None,
        provider_model: str | None,
        route_reason: str,
    ) -> AttemptLease:
        self.events.append(
            {
                "context": context,
                "request": asdict(request),
                "provider": provider_name,
                "model": provider_model,
                "reason": route_reason,
            }
        )
        return AttemptLease(attempt_id=self.attempt_id, lease_owner="recording-owner")

    def heartbeat(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
    ) -> AttemptHeartbeat:
        self.events.append((lease, context, AttemptHeartbeat.ACTIVE))
        return AttemptHeartbeat.ACTIVE

    def succeed(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
        result: AttemptSuccessAudit,
        *,
        latency_ms: int,
    ) -> AttemptCompletion:
        self.events.append((lease, context, result.usage, latency_ms))
        return AttemptCompletion.SUCCEEDED

    def fail(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
        error: ModelGatewayError,
        *,
        latency_ms: int,
    ) -> None:
        self.events.append((lease, context, error.code, latency_ms))


async def test_openai_compatible_provider_uses_prompt_safe_gateway_audit_port() -> None:
    private_prompt = "PRIVATE_OPENAI_PROMPT"
    private_response = "PRIVATE_OPENAI_RESPONSE"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "provider-request-1",
                "model": "provider/actual",
                "choices": [{"message": {"content": private_response}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 2,
                    "total_tokens": 7,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleTextProvider(
        OpenAICompatibleConfig(
            provider_name="provider-test",
            base_url="https://provider.test/v1",
            model="provider/model",
            api_key=SecretStr("test-only-key"),
            timeout_seconds=5,
        ),
        client=client,
    )
    sink = RecordingAuditSink()
    gateway = ModelGateway({ModelCapability.TEXT_SMOKE: provider}, audit_sink=sink)
    try:
        result = await gateway.generate_text(
            TextModelRequest(
                capability=ModelCapability.TEXT_SMOKE,
                request_id="req-openai-audit",
                prompt=private_prompt,
            ),
            audit_context=ModelAuditContext(
                organization_id=UUID("01980000-0000-7000-8000-000000000010"),
                user_id=UUID("01980000-0000-7000-8000-000000000011"),
                project_id=UUID("01980000-0000-7000-8000-000000000012"),
                node_run_id=UUID("01980000-0000-7000-8000-000000000013"),
                generation_job_id=None,
            ),
        )
    finally:
        await client.aclose()

    assert result.text == private_response
    rendered_events = repr(sink.events)
    assert private_prompt not in rendered_events
    assert private_response not in rendered_events
    assert "req-openai-audit" in rendered_events
    assert len(sink.events) == 2
