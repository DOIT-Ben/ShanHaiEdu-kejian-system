"""Stable API errors that never expose internal exception text."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


def error_response(request: Request, error: ApiError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "req_unavailable")
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable,
                "details": error.details,
            },
            "request_id": request_id,
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        return error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        details = {
            "fields": [
                {
                    "location": [str(part) for part in item.get("loc", ())],
                    "message": str(item.get("msg", "invalid value")),
                    "type": str(item.get("type", "validation_error")),
                }
                for item in error.errors()
            ]
        }
        return error_response(
            request,
            ApiError(
                status_code=422,
                code="VALIDATION_FAILED",
                message="The request does not match the API contract.",
                details=details,
            ),
        )
