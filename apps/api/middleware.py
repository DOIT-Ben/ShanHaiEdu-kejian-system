"""HTTP middleware used by the API bootstrap."""

from __future__ import annotations

import logging
from time import perf_counter

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from apps.api.request_context import (
    REQUEST_ID_HEADER,
    request_id_context,
    resolve_request_id,
)

logger = logging.getLogger(__name__)


class SessionLoginBodyLimitMiddleware:
    """Reject oversized login bodies before JSON parsing or credential handling."""

    def __init__(self, app: ASGIApp, *, max_bytes: int = 2_048) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != "/api/v2/auth/session"
        ):
            await self._app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                await self._reject(scope, receive, send)
                return

        received = 0

        async def receive_limited() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    raise _SessionLoginBodyTooLarge
            return message

        try:
            await self._app(scope, receive_limited, send)
        except _SessionLoginBodyTooLarge:
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        request_id = scope.get("state", {}).get("request_id", "req_unavailable")
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "REQUEST_TOO_LARGE",
                    "message": "The login request body is too large.",
                    "retryable": False,
                    "details": {},
                },
                "request_id": request_id,
            },
        )
        await response(scope, receive, send)


class _SessionLoginBodyTooLarge(Exception):
    pass


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        started_at = perf_counter()
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            logger.info(
                "http_request_completed",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": response.status_code,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )
            return response
        except Exception:
            logger.exception(
                "http_request_failed",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )
            raise
        finally:
            request_id_context.reset(token)
