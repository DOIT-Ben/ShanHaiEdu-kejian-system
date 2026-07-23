"""Deterministic projection from published page facts to the frozen render Port."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast
from uuid import UUID

from apps.api.assets.ppt_runtime_contracts import PptBackgroundFact
from apps.api.ppt_rendering import (
    AssemblyRequest,
    BackgroundImage,
    Box,
    CanvasSpec,
    FontStyle,
    PageSpec,
    ShapeElement,
    TextElement,
)

_PAGE_X = 685_800
_PAGE_WIDTH = 10_820_400
_TITLE_Y = 548_640
_TITLE_HEIGHT = 685_800
_CONTENT_HEIGHT = 502_920
_CONTENT_FIRST_Y = 5_074_920
_CONTENT_SECOND_Y = 5_760_720


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
    title = _text(source.get("teaching_task"))
    editable = (
        *_items(source.get("editable_text_blocks")),
        *_items(source.get("editable_math_shapes")),
    )
    elements = _base_elements(
        page_key=page_key,
        page_type=_text(source.get("page_type")),
        title=title,
        editable_count=len(editable),
    )
    for index, item in enumerate(editable):
        elements.extend(
            _editable_elements(
                item,
                index=index,
                count=len(editable),
            )
        )
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


def _base_elements(
    *,
    page_key: str,
    page_type: str,
    title: str,
    editable_count: int,
) -> list[TextElement | ShapeElement]:
    if page_type == "cover":
        return [
            TextElement(
                element_key=f"{page_key}.teaching_task",
                kind="title",
                text=title,
                box=Box(x=6_400_800, y=914_400, width=4_800_600, height=914_400),
                font=FontStyle(
                    size_points=_title_size(title),
                    bold=True,
                    color="17365D",
                ),
            )
        ]
    panel_y = 4_846_320 if editable_count > 1 else 5_303_520
    panel_height = 1_508_760 if editable_count > 1 else 1_051_560
    return [
        ShapeElement(
            element_key=f"{page_key}.title_backplate",
            kind="rectangle",
            box=Box(x=548_640, y=457_200, width=11_094_720, height=960_120),
            fill_color="FFFFFF",
            line_color="FFFFFF",
        ),
        ShapeElement(
            element_key=f"{page_key}.content_backplate",
            kind="rectangle",
            box=Box(x=548_640, y=panel_y, width=11_094_720, height=panel_height),
            fill_color="FFFFFF",
            line_color="FFFFFF",
        ),
        TextElement(
            element_key=f"{page_key}.teaching_task",
            kind="title",
            text=title,
            box=Box(x=_PAGE_X, y=_TITLE_Y, width=_PAGE_WIDTH, height=_TITLE_HEIGHT),
            font=FontStyle(
                size_points=_title_size(title),
                bold=True,
                color="17365D",
            ),
        ),
    ]


def _editable_elements(
    item: Mapping[str, Any],
    *,
    index: int,
    count: int,
) -> list[TextElement | ShapeElement]:
    key = _text(item.get("element_key"))
    responsibility = _text(item.get("responsibility"))
    content = _text(item.get("content"))
    y = 5_531_520 if count == 1 else (_CONTENT_FIRST_Y if index == 0 else _CONTENT_SECOND_Y)
    if responsibility == "EDITABLE_MATH":
        return [
            TextElement(
                element_key=key,
                kind="number" if "MATH" in key else "body",
                text=content,
                box=Box(x=_PAGE_X, y=y, width=_PAGE_WIDTH, height=_CONTENT_HEIGHT),
                font=FontStyle(size_points=_content_size(content), color="203864"),
            )
        ]
    if responsibility != "EDITABLE_DIAGRAM":
        raise _invalid("the page declares an unsupported editable responsibility")
    return [
        ShapeElement(
            element_key=key,
            kind="rectangle",
            box=Box(x=_PAGE_X, y=y + 68_580, width=365_760, height=365_760),
            fill_color="E2F0D9",
            line_color="2F6B5F",
            line_width_points=2,
        ),
        TextElement(
            element_key=f"{key}.label",
            kind="annotation",
            text=content,
            box=Box(
                x=_PAGE_X + 548_640,
                y=y,
                width=_PAGE_WIDTH - 548_640,
                height=_CONTENT_HEIGHT,
            ),
            font=FontStyle(size_points=_content_size(content), color="203864"),
        ),
    ]


def _title_size(text: str) -> int:
    if len(text) <= 18:
        return 26
    if len(text) <= 26:
        return 23
    return 20


def _content_size(text: str) -> int:
    return 18 if len(text) <= 30 else 16


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
