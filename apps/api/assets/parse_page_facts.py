"""Bounded teacher-visible facts from one exact material parse."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from apps.api.assets.models import MaterialParseVersion
from apps.api.assets.schemas import MaterialParsePageRead
from apps.api.errors import ApiError

TEXT_PREVIEW_LIMIT = 1_000


def read_material_parse_pages(parse: MaterialParseVersion) -> list[MaterialParsePageRead]:
    if parse.status != "succeeded":
        raise ApiError(
            status_code=409,
            code="MATERIAL_PARSE_NOT_READY",
            message="The material parse has not succeeded.",
        )
    content = parse.content_json
    if not isinstance(content, Mapping):
        raise _invalid()
    raw_pages = cast(Mapping[str, object], content).get("pages")
    if not isinstance(raw_pages, Sequence) or isinstance(raw_pages, (str, bytes)):
        raise _invalid()
    pages = [_read_page(value) for value in cast(Sequence[object], raw_pages)]
    pages.sort(key=lambda page: page.page_number)
    if len({page.page_number for page in pages}) != len(pages):
        raise _invalid()
    return pages


def _read_page(value: object) -> MaterialParsePageRead:
    if not isinstance(value, Mapping):
        raise _invalid()
    page = cast(Mapping[str, object], value)
    page_number = page.get("page_number")
    raw_blocks = page.get("text_blocks")
    raw_images = page.get("image_references")
    if (
        type(page_number) is not int
        or page_number < 1
        or not isinstance(raw_blocks, Sequence)
        or isinstance(raw_blocks, (str, bytes))
        or not isinstance(raw_images, Sequence)
        or isinstance(raw_images, (str, bytes))
    ):
        raise _invalid()
    blocks = cast(Sequence[object], raw_blocks)
    images = cast(Sequence[object], raw_images)
    if any(not isinstance(item, Mapping) for item in images):
        raise _invalid()
    text_parts: list[str] = []
    for value in blocks:
        if not isinstance(value, Mapping):
            raise _invalid()
        text = cast(Mapping[str, object], value).get("text")
        if not isinstance(text, str):
            raise _invalid()
        text_parts.append(text)
    return MaterialParsePageRead(
        page_number=page_number,
        text_preview="".join(text_parts).strip()[:TEXT_PREVIEW_LIMIT],
        text_block_count=len(blocks),
        image_count=len(images),
    )


def _invalid() -> ApiError:
    return ApiError(
        status_code=409,
        code="MATERIAL_PARSE_EVIDENCE_INVALID",
        message="The material parse evidence is unavailable.",
    )
