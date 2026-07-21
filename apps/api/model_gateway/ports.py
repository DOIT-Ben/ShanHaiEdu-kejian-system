"""Interfaces implemented by providers and cancellation sources."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from apps.api.model_gateway.contracts import (
    ImageModelRequest,
    ImageProviderResult,
    TextModelRequest,
    TextProviderResult,
    VideoModelRequest,
    VideoPollRequest,
    VideoProviderResult,
)


class CancellationToken(Protocol):
    @property
    def cancelled(self) -> bool: ...


class ProviderMetadata(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...


class TextProvider(ProviderMetadata, Protocol):
    async def complete(self, request: TextModelRequest) -> TextProviderResult: ...


class ImageProvider(ProviderMetadata, Protocol):
    async def generate(self, request: ImageModelRequest) -> ImageProviderResult: ...


class VideoProvider(ProviderMetadata, Protocol):
    async def submit(
        self,
        request: VideoModelRequest,
        *,
        organization_id: UUID | None = None,
    ) -> VideoProviderResult: ...

    async def poll(self, request: VideoPollRequest) -> VideoProviderResult: ...

    async def cancel(self, request: VideoPollRequest) -> VideoProviderResult: ...
