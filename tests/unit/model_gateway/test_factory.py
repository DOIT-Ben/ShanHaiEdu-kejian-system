from __future__ import annotations

import pytest

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelCapability,
    ModelGatewayError,
)
from apps.api.model_gateway.factory import (
    build_provider_media_reference_resolver,
    build_real_text_gateway,
)
from apps.api.settings import Settings
from tests.fakes.object_storage import FakeObjectStorage


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


async def test_real_gateway_routes_all_stage2_text_capabilities(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_TEST_SECRET", "configured")
    configured = Settings(
        _env_file=None,
        environment="test",
        text_provider_name="newapi",
        text_provider_base_url="https://provider.test/api/v1",
        text_provider_model="deepseek-v3",
        text_provider_secret_env="PROVIDER_TEST_SECRET",
    )

    gateway, provider = build_real_text_gateway(configured)
    try:
        assert set(gateway._text_routes) == {
            ModelCapability.TEXT_SMOKE,
            ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH,
            ModelCapability.TEXT_STRUCTURED_CREATIVE_EDUCATION,
        }
    finally:
        await provider.aclose()


def test_provider_media_resolver_requires_server_only_route_and_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    storage = FakeObjectStorage()
    missing_route = Settings(_env_file=None, environment="test")
    with pytest.raises(ModelGatewayError) as missing_config:
        build_provider_media_reference_resolver(
            missing_route,
            session=object(),
            storage=storage,
        )
    assert missing_config.value.code == GatewayErrorCode.ROUTE_UNAVAILABLE

    configured = Settings(
        _env_file=None,
        environment="test",
        provider_media_root=tmp_path,
        provider_media_public_base_url="https://relay.test/provider-media",
        provider_media_signing_secret_env="PROVIDER_MEDIA_TEST_SECRET",
    )
    monkeypatch.delenv("PROVIDER_MEDIA_TEST_SECRET", raising=False)
    with pytest.raises(ModelGatewayError) as missing_secret:
        build_provider_media_reference_resolver(
            configured,
            session=object(),
            storage=storage,
        )
    assert missing_secret.value.code == GatewayErrorCode.ROUTE_UNAVAILABLE
