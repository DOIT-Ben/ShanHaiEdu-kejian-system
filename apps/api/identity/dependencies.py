"""FastAPI authentication and actor dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session, sessionmaker

from apps.api.errors import ApiError
from apps.api.identity.authentication import Authenticator
from apps.api.identity.context import ActorContext, AuthenticatedIdentity
from apps.api.identity.repository import IdentityRepository

session_cookie = APIKeyCookie(
    name="shanhai_session",
    scheme_name="cookieAuth",
    description="Secure HttpOnly session established by the configured authentication provider.",
    auto_error=False,
)


async def get_authenticated_identity(
    request: Request,
    token: Annotated[str | None, Security(session_cookie)],
) -> AuthenticatedIdentity:
    authenticator = cast(Authenticator | None, request.app.state.authenticator)
    if authenticator is None or token is None:
        raise authentication_required()
    identity = await authenticator.authenticate(token)
    if identity is None:
        raise authentication_required()
    return identity


def get_identity_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session] | None, request.app.state.session_factory)
    if factory is None:
        raise ApiError(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="Database persistence is not configured.",
            retryable=True,
        )
    with factory() as session:
        yield session


def get_actor_context(
    identity: Annotated[AuthenticatedIdentity, Depends(get_authenticated_identity)],
    session: Annotated[Session, Depends(get_identity_session)],
) -> ActorContext:
    return IdentityRepository(session).resolve_actor(identity)


def authentication_required() -> ApiError:
    return ApiError(
        status_code=401,
        code="AUTHENTICATION_REQUIRED",
        message="Authentication is required for this request.",
    )
