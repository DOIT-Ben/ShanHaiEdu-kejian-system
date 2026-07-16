"""Request-scoped application dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from apps.api.errors import ApiError
from apps.api.uploads.storage import ObjectStorage


def get_session(request: Request) -> Iterator[Session]:
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


def get_object_storage(request: Request) -> ObjectStorage:
    storage = cast(ObjectStorage | None, request.app.state.object_storage)
    if storage is None:
        raise ApiError(
            status_code=503,
            code="OBJECT_STORAGE_UNAVAILABLE",
            message="Object storage is not configured.",
            retryable=True,
        )
    return storage
