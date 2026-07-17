"""Authentication adapter port; provider-specific code implements this protocol."""

from __future__ import annotations

from typing import Protocol

from apps.api.identity.context import AuthenticatedIdentity


class Authenticator(Protocol):
    async def authenticate(self, session_token: str) -> AuthenticatedIdentity | None: ...
