"""HTTP cursor parsing shared by project-scoped list endpoints."""

from __future__ import annotations

from uuid import UUID

from apps.api.errors import ApiError


def parse_uuid_page_cursor(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError as exc:
        raise ApiError(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The page cursor is invalid.",
            details={"field": "page[cursor]"},
        ) from exc
