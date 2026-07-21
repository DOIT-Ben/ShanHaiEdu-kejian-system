"""Server-side private media setup for the explicit administrative smoke."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from apps.api.assets.provider_media import SqlAlchemyProviderMediaAssetReader
from apps.api.database import build_engine, build_session_factory
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    MediaReference,
    ModelGatewayError,
)
from apps.api.model_gateway.factory import build_provider_media_reference_resolver
from apps.api.model_gateway.provider_media import ProviderMediaReferenceResolver
from apps.api.settings import Settings
from apps.api.uploads.storage import build_object_storage


@dataclass(frozen=True, slots=True)
class VideoSmokeMediaContext:
    organization_id: UUID
    reference: MediaReference
    resolver: ProviderMediaReferenceResolver


@contextmanager
def open_video_smoke_media_context(
    settings: Settings,
    *,
    organization_id: UUID | None,
    file_version_id: UUID | None,
) -> Generator[VideoSmokeMediaContext | None]:
    if organization_id is None and file_version_id is None:
        yield None
        return
    if organization_id is None or file_version_id is None or settings.database_url is None:
        raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
    storage = build_object_storage(settings)
    if storage is None:
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    engine = build_engine(settings.database_url.get_secret_value())
    session = build_session_factory(engine)()
    try:
        version = SqlAlchemyProviderMediaAssetReader(session).get_clean_image_version(
            organization_id=organization_id,
            file_version_id=file_version_id,
        )
        if version is None:
            raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
        yield VideoSmokeMediaContext(
            organization_id=organization_id,
            reference=MediaReference(file_version_id=file_version_id, mime_type=version.mime_type),
            resolver=build_provider_media_reference_resolver(
                settings,
                session=session,
                storage=storage,
            ),
        )
    finally:
        session.close()
        engine.dispose()
