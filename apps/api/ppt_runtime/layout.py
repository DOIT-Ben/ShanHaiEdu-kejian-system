"""Deterministic projection from published page facts to the frozen render Port."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast
from uuid import UUID

from apps.api.assets.ppt_runtime_contracts import PptBackgroundFact
from apps.api.ppt_rendering.models import (
    AssemblyRequest,
    BackgroundImage,
    Box,
    CanvasSpec,
    FontStyle,
    PageSpec,
    ShapeElement,
    TextElement,
)

_PAGE_X = 914_400
_PAGE_WIDTH = 10_363_200
_TITLE_Y = 571_500
_TITLE_HEIGHT = 685_800
_CONTENT_Y = 1_600_200
_CONTENT_HEIGHT = 914_400
_CONTENT_GAP = 228_600


class PptLayoutError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def build_assembly_request(
    page_spec_content: Mapping[str, Any],
    backgrounds: tuple[PptBackgroundFact, ...],
    payloads: Mapping[UUID, bytes],
) -> AssemblyRequest:
    pages = _page_specs(page_spec_content)
    if len(pages) != len(backgrounds):
        raise _invalid("the page and exact background counts differ")
    rendered: list[PageSpec] = []
    for page, background in zip(pages, backgrounds, strict=True):
        if (
            _text(page.get("page_key")) != background.page_key
            or _positive_int(page.get("page_position")) != background.position
        ):
            raise _invalid("the exact background order differs from the page specification")
        payload = payloads.get(background.file_asset_version_id)
        if (
            payload is None
            or len(payload) != background.size_bytes
            or hashlib.sha256(payload).hexdigest() != background.sha256
        ):
            raise _invalid("an exact background payload differs from its immutable file fact")
        rendered.append(_page(page, background, payload))
    return AssemblyRequest(canvas=CanvasSpec(), pages=tuple(rendered))


def _page(
    source: Mapping[str, Any],
    background: PptBackgroundFact,
    payload: bytes,
) -> PageSpec:
    canvas = _mapping(source.get("canvas"))
    if canvas.get("aspect_ratio") != "16:9":
        raise _invalid("the page does not use the published 16:9 canvas")
    page_key = _text(source.get("page_key"))
    position = _positive_int(source.get("page_position"))
    elements: list[TextElement | ShapeElement] = [
        TextElement(
            element_key=f"{page_key}.teaching_task",
            kind="title",
            text=_text(source.get("teaching_task")),
            box=Box(x=_PAGE_X, y=_TITLE_Y, width=_PAGE_WIDTH, height=_TITLE_HEIGHT),
            font=FontStyle(size_points=28, bold=True, color="17365D"),
        )
    ]
    editable = (
        *_items(source.get("editable_text_blocks")),
        *_items(source.get("editable_math_shapes")),
    )
    for index, item in enumerate(editable):
        elements.extend(_editable_elements(item, index=index))
    return PageSpec(
        page_key=page_key,
        position=position,
        backgrounds=(
            BackgroundImage(
                content=payload, media_type=_background_media_type(background.mime_type)
            ),
        ),
        elements=tuple(elements),
    )


def _editable_elements(item: Mapping[str, Any], *, index: int) -> list[TextElement | ShapeElement]:
    key = _text(item.get("element_key"))
    responsibility = _text(item.get("responsibility"))
    content = _text(item.get("content"))
    y = _CONTENT_Y + index * (_CONTENT_HEIGHT + _CONTENT_GAP)
    if responsibility == "EDITABLE_MATH":
        return [
            TextElement(
                element_key=key,
                kind="number" if "MATH" in key else "body",
                text=content,
                box=Box(x=_PAGE_X, y=y, width=_PAGE_WIDTH, height=_CONTENT_HEIGHT),
                font=FontStyle(size_points=22, color="203864"),
            )
        ]
    if responsibility != "EDITABLE_DIAGRAM":
        raise _invalid("the page declares an unsupported editable responsibility")
    return [
        ShapeElement(
            element_key=key,
            kind="rectangle",
            box=Box(x=_PAGE_X, y=y, width=3_200_400, height=_CONTENT_HEIGHT),
            fill_color="E2F0D9",
            line_color="2F6B5F",
            line_width_points=2,
        ),
        TextElement(
            element_key=f"{key}.label",
            kind="annotation",
            text=content,
            box=Box(
                x=_PAGE_X + 3_429_000,
                y=y,
                width=_PAGE_WIDTH - 3_429_000,
                height=_CONTENT_HEIGHT,
            ),
            font=FontStyle(size_points=18, color="203864"),
        ),
    ]


def _page_specs(content: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = content.get("page_specs")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)) or not raw:
        raise _invalid("the exact page specification set is missing")
    values = tuple(cast(Sequence[object], raw))
    if any(not isinstance(value, Mapping) for value in values):
        raise _invalid("the exact page specification set is invalid")
    return cast(tuple[Mapping[str, Any], ...], values)


def _items(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise _invalid("the editable element declaration is invalid")
    items = tuple(cast(Sequence[object], value))
    if any(not isinstance(item, Mapping) for item in items):
        raise _invalid("the editable element declaration is invalid")
    return cast(tuple[Mapping[str, Any], ...], items)


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _invalid("the page canvas declaration is invalid")
    return cast(Mapping[str, Any], value)


def _text(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise _invalid("a required page text fact is missing")
    return value


def _positive_int(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise _invalid("a required page position is invalid")
    return value


def _background_media_type(value: str) -> Literal["image/png", "image/jpeg"]:
    if value not in {"image/png", "image/jpeg"}:
        raise _invalid("the exact background media type is unsupported")
    return cast(Literal["image/png", "image/jpeg"], value)


def _invalid(message: str) -> PptLayoutError:
    return PptLayoutError("PPT_RUNTIME_PAGE_LAYOUT_INVALID", message)
