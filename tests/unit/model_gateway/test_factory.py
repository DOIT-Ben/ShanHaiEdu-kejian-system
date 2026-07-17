from __future__ import annotations

import pytest

from apps.api.model_gateway.contracts import GatewayErrorCode, ModelGatewayError
from apps.api.model_gateway.factory import build_real_text_gateway
from apps.api.settings import Settings


def test_real_gateway_requires_route_and_secret_reference(monkeypatch) -> None:
    settings = Settings(_env_file=None, environment="test")
    with pytest.raises(ModelGatewayError) as missing_route:
        build_real_text_gateway(settings)
    assert missing_route.value.code == GatewayErrorCode.ROUTE_UNAVAILABLE

    configured = Settings(
        _env_file=None,
        environment="test",
        text_provider_name="provider-test",
        text_provider_base_url="https://provider.test/api/v1",
        text_provider_model="provider/model",
        text_provider_secret_env="PROVIDER_TEST_SECRET",
    )
    monkeypatch.delenv("PROVIDER_TEST_SECRET", raising=False)
    with pytest.raises(ModelGatewayError) as missing_secret:
        build_real_text_gateway(configured)
    assert missing_secret.value.code == GatewayErrorCode.ROUTE_UNAVAILABLE
