"""Interfaces implemented by providers and cancellation sources."""

from __future__ import annotations

from typing import Protocol

from apps.api.model_gateway.contracts import TextModelRequest, TextProviderResult


class CancellationToken(Protocol):
    @property
    def cancelled(self) -> bool: ...


class TextProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    async def complete(self, request: TextModelRequest) -> TextProviderResult: ...
