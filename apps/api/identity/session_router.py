"""Production session lifecycle endpoints."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Request, Response, Security, status

from apps.api.errors import ApiError
from apps.api.identity.dependencies import session_cookie
from apps.api.identity.session_schemas import (
    CreateSessionRequest,
    CurrentSession,
    SessionEnvelope,
    SessionPrincipal,
)
from apps.api.identity.session_service import DatabaseSessionService, SessionSnapshot
from apps.api.settings import Settings

router = APIRouter(prefix="/api/v2/auth/session", tags=["identity"])
_NO_STORE_RESPONSE = {
    "headers": {"Cache-Control": {"schema": {"type": "string", "const": "no-store"}}}
}


@router.post(
    "",
    response_model=SessionEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="createSession",
    responses={status.HTTP_201_CREATED: _NO_STORE_RESPONSE},
)
def create_session(
    payload: CreateSessionRequest,
    request: Request,
    response: Response,
) -> SessionEnvelope:
    service = require_session_service(request)
    service.require_origin(request.headers.get("Origin"))
    source_ip = service.source_ip(
        request.client.host if request.client is not None else None,
        request.headers.get("X-Forwarded-For"),
    )
    raw_token, snapshot = service.create_session(
        access_code=payload.access_code,
        existing_token=request.cookies.get("shanhai_session"),
        source_ip=source_ip,
    )
    settings = cast(Settings, request.app.state.settings)
    response.set_cookie(
        key="shanhai_session",
        value=raw_token,
        max_age=settings.session_ttl_seconds,
        expires=snapshot.expires_at,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    prevent_session_response_caching(response)
    return present_session(request, snapshot)


@router.get(
    "",
    response_model=SessionEnvelope,
    operation_id="getCurrentSession",
    responses={status.HTTP_200_OK: _NO_STORE_RESPONSE},
)
def get_current_session(
    request: Request,
    response: Response,
    token: Annotated[str | None, Security(session_cookie)],
) -> SessionEnvelope:
    snapshot = require_session_service(request).require_snapshot(token)
    prevent_session_response_caching(response)
    return present_session(request, snapshot)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteSession",
    responses={status.HTTP_204_NO_CONTENT: _NO_STORE_RESPONSE},
)
def delete_session(
    request: Request,
    response: Response,
    token: Annotated[str | None, Security(session_cookie)],
) -> None:
    require_session_service(request).revoke(token)
    settings = cast(Settings, request.app.state.settings)
    response.delete_cookie(
        key="shanhai_session",
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    prevent_session_response_caching(response)


def require_session_service(request: Request) -> DatabaseSessionService:
    service = cast(DatabaseSessionService | None, request.app.state.session_service)
    if service is None:
        raise ApiError(
            status_code=503,
            code="AUTHENTICATION_UNAVAILABLE",
            message="Session authentication is not configured.",
            retryable=True,
        )
    return service


def present_session(request: Request, snapshot: SessionSnapshot) -> SessionEnvelope:
    return SessionEnvelope(
        data=CurrentSession(
            session_id=snapshot.session_id,
            principal=SessionPrincipal(
                principal_id=snapshot.principal_id,
                user_id=snapshot.user_id,
                organization_id=snapshot.organization_id,
                display_name=snapshot.display_name,
                organization_name=snapshot.organization_name,
                organization_role=snapshot.organization_role,
            ),
            expires_at=snapshot.expires_at,
            csrf_token=snapshot.csrf_token,
        ),
        request_id=request.state.request_id,
    )


def prevent_session_response_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
