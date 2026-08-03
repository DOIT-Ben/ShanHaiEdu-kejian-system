"""Decode immutable material parse inputs from a generation job."""

from __future__ import annotations

from typing import Protocol, cast
from uuid import UUID

from apps.api.assets.material_parser import MaterialParserError


class MaterialParseJobInput(Protocol):
    @property
    def creation_request_json(self) -> object: ...


def exact_file_version_id(job: MaterialParseJobInput) -> UUID | None:
    request = cast(dict[str, object] | None, job.creation_request_json)
    if request is None or "file_asset_version_id" not in request:
        return None
    value = request["file_asset_version_id"]
    if not isinstance(value, str):
        raise MaterialParserError("PDF_SOURCE_UNAVAILABLE")
    try:
        return UUID(value)
    except ValueError as exc:
        raise MaterialParserError("PDF_SOURCE_UNAVAILABLE") from exc
