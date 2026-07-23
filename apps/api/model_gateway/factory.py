"""Build configured gateway routes without exposing secret values."""

from __future__ import annotations

import os

from pydantic import SecretStr
from sqlalchemy.orm import Session

from apps.api.assets.provider_media import SqlAlchemyProviderMediaAssetReader
from apps.api.model_gateway.audit_contracts import AttemptAuditSink
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelCapability,
    ModelGatewayError,
)
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.model_gateway.newapi_video import (
    NewApiVideoConfig,
    NewApiVideoProvider,
    VideoResultStore,
)
from apps.api.model_gateway.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleTextProvider,
)
from apps.api.model_gateway.provider_media import (
    ProviderMediaReferenceResolver,
    ProviderMediaResolverConfig,
)
from apps.api.settings import Settings
from apps.api.uploads.storage import ObjectStorage


def build_real_text_gateway(
    settings: Settings,
    *,
    audit_sink: AttemptAuditSink | None = None,
) -> tuple[ModelGateway, OpenAICompatibleTextProvider]:
    if not (
        settings.text_provider_name
        and settings.text_provider_base_url
        and settings.text_provider_model
    ):
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    secret = os.environ.get(settings.text_provider_secret_env)
    if not secret:
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    provider = OpenAICompatibleTextProvider(
        OpenAICompatibleConfig(
            provider_name=settings.text_provider_name,
            base_url=str(settings.text_provider_base_url),
            model=settings.text_provider_model,
            api_key=SecretStr(secret),
            timeout_seconds=settings.text_provider_timeout_seconds,
        )
    )
    return (
        ModelGateway(
            {
                ModelCapability.TEXT_SMOKE: provider,
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider,
                ModelCapability.TEXT_STRUCTURED_CREATIVE_EDUCATION: provider,
            },
            audit_sink=audit_sink,
        ),
        provider,
    )


def build_real_video_gateway(
    settings: Settings,
    *,
    store: VideoResultStore,
    media_reference_resolver: ProviderMediaReferenceResolver | None = None,
) -> tuple[ModelGateway, NewApiVideoProvider]:
    if not (
        settings.video_provider_name
        and settings.video_provider_base_url
        and settings.video_provider_model
    ):
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    secret = os.environ.get(settings.video_provider_secret_env)
    if not secret:
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    provider = NewApiVideoProvider(
        NewApiVideoConfig(
            provider_name=settings.video_provider_name,
            base_url=str(settings.video_provider_base_url),
            model=settings.video_provider_model,
            api_key=SecretStr(secret),
            timeout_seconds=settings.video_provider_timeout_seconds,
            max_download_bytes=settings.video_provider_max_download_bytes,
        ),
        store=store,
        media_reference_resolver=media_reference_resolver,
    )
    return (
        ModelGateway(
            {},
            video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: provider},
        ),
        provider,
    )


def build_provider_media_reference_resolver(
    settings: Settings,
    *,
    session: Session,
    storage: ObjectStorage,
) -> ProviderMediaReferenceResolver:
    if settings.provider_media_root is None or settings.provider_media_public_base_url is None:
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    secret = os.environ.get(settings.provider_media_signing_secret_env)
    if not secret:
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    return ProviderMediaReferenceResolver(
        asset_reader=SqlAlchemyProviderMediaAssetReader(session),
        storage=storage,
        config=ProviderMediaResolverConfig(
            relay_root=settings.provider_media_root,
            public_base_url=str(settings.provider_media_public_base_url),
            signing_secret=secret,
            ttl_seconds=settings.provider_media_max_ttl_seconds,
            max_file_bytes=settings.provider_media_max_file_bytes,
        ),
    )
