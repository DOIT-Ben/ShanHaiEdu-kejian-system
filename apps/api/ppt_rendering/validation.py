"""Fail-closed validation and canonical manifest construction."""

from __future__ import annotations

import hashlib
import json
import re

from apps.api.ppt_rendering.errors import PptRenderingError
from apps.api.ppt_rendering.images import ImageInfo, inspect_background
from apps.api.ppt_rendering.models import (
    IMPLEMENTATION_VERSION,
    MAX_BACKGROUND_BYTES,
    MAX_ELEMENTS_PER_PAGE,
    MAX_PAGES,
    MAX_TOTAL_INPUT_BYTES,
    SLIDE_HEIGHT_EMU,
    SLIDE_WIDTH_EMU,
    AssemblyManifest,
    AssemblyRequest,
    ManifestElement,
    ManifestPage,
    PageSpec,
    ShapeElement,
    TextElement,
)

_COLOR = re.compile(r"^[0-9A-F]{6}$")


def build_manifest(request: AssemblyRequest) -> AssemblyManifest:
    image_info = _validate_request(request)
    pages = tuple(
        _manifest_page(page, info) for page, info in zip(request.pages, image_info, strict=True)
    )
    payload = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "canvas": request.canvas.model_dump(mode="json"),
        "pages": [page.model_dump(mode="json") for page in pages],
    }
    content_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return AssemblyManifest(
        implementation_version=IMPLEMENTATION_VERSION,
        content_hash=content_hash,
        canvas=request.canvas,
        pages=pages,
    )


def _validate_request(request: AssemblyRequest) -> tuple[ImageInfo, ...]:
    _validate_hash_text_encoding(request)
    _validate_limits(request)
    canvas = request.canvas
    if canvas.width != SLIDE_WIDTH_EMU or canvas.height != SLIDE_HEIGHT_EMU:
        raise PptRenderingError(
            "PPT_CANVAS_ASPECT_RATIO_INVALID", "canvas must use the canonical 16:9 dimensions"
        )
    if canvas.safe_margin < 0 or canvas.safe_margin * 2 >= min(canvas.width, canvas.height):
        raise PptRenderingError("PPT_CANVAS_SAFE_AREA_INVALID", "canvas safe area is invalid")
    if not request.pages:
        raise PptRenderingError("PPT_PAGES_REQUIRED", "at least one page is required")

    page_keys: set[str] = set()
    image_info: list[ImageInfo] = []
    for expected_position, page in enumerate(request.pages, start=1):
        if not page.page_key.strip():
            raise PptRenderingError("PPT_PAGE_KEY_REQUIRED", "page_key is required")
        if page.page_key in page_keys:
            raise PptRenderingError("PPT_PAGE_KEY_DUPLICATE", "page_key must be unique")
        page_keys.add(page.page_key)
        if page.position != expected_position:
            raise PptRenderingError(
                "PPT_PAGE_ORDER_INVALID", "page positions must be consecutive and ordered"
            )
        image_info.append(_validate_page(request, page))
    return tuple(image_info)


def _validate_page(request: AssemblyRequest, page: PageSpec) -> ImageInfo:
    backgrounds = page.backgrounds
    if not backgrounds:
        raise PptRenderingError("PPT_PAGE_BACKGROUND_REQUIRED", "each page needs one background")
    if len(backgrounds) > 1:
        raise PptRenderingError("PPT_PAGE_BACKGROUND_MULTIPLE", "each page allows one background")
    image_info: ImageInfo | None = None
    for background in backgrounds:
        image_info = inspect_background(background)

    element_keys: set[str] = set()
    for element in page.elements:
        if element.element_key in element_keys:
            raise PptRenderingError("PPT_ELEMENT_KEY_DUPLICATE", "element keys must be unique")
        element_keys.add(element.element_key)
        _validate_element(request, element)
    if image_info is None:
        raise PptRenderingError("PPT_PAGE_BACKGROUND_REQUIRED", "each page needs one background")
    return image_info


def _validate_element(request: AssemblyRequest, element: TextElement | ShapeElement) -> None:
    box = element.box
    margin = request.canvas.safe_margin
    if (
        box.x < margin
        or box.y < margin
        or box.width <= 0
        or box.height <= 0
        or box.x + box.width > request.canvas.width - margin
        or box.y + box.height > request.canvas.height - margin
    ):
        raise PptRenderingError(
            "PPT_ELEMENT_OUT_OF_BOUNDS", "editable element must remain inside the safe area"
        )
    _validate_xml_text(element.element_key)
    if isinstance(element, TextElement):
        _validate_xml_text(element.text)
        _validate_xml_text(element.font.family)
        if not element.text.strip():
            raise PptRenderingError("PPT_TEXT_REQUIRED", "text elements cannot be blank")
        if not _COLOR.fullmatch(element.font.color):
            raise PptRenderingError("PPT_COLOR_INVALID", "font color must be six hex digits")
    elif not _COLOR.fullmatch(element.line_color) or (
        element.fill_color is not None and not _COLOR.fullmatch(element.fill_color)
    ):
        raise PptRenderingError("PPT_COLOR_INVALID", "shape colors must be six hex digits")


def _manifest_page(page: PageSpec, image_info: ImageInfo) -> ManifestPage:
    background = page.backgrounds[0]
    elements = tuple(
        ManifestElement(
            element_key=element.element_key,
            element_type=element.element_type,
            kind=element.kind,
            editability=(
                "editable_text_fallback"
                if isinstance(element, TextElement) and element.kind == "formula"
                else "native"
            ),
            box=element.box,
            text=element.text if isinstance(element, TextElement) else None,
            font=element.font if isinstance(element, TextElement) else None,
            fill_color=element.fill_color if isinstance(element, ShapeElement) else None,
            line_color=element.line_color if isinstance(element, ShapeElement) else None,
            line_width_points=(
                element.line_width_points if isinstance(element, ShapeElement) else None
            ),
        )
        for element in page.elements
    )
    return ManifestPage(
        page_key=page.page_key,
        position=page.position,
        background_sha256=hashlib.sha256(background.content).hexdigest(),
        background_media_type=background.media_type,
        background_size_bytes=len(background.content),
        background_width=image_info.width,
        background_height=image_info.height,
        elements=elements,
    )


def _validate_limits(request: AssemblyRequest) -> None:
    if len(request.pages) > MAX_PAGES:
        raise PptRenderingError("PPT_PAGE_LIMIT_EXCEEDED", "page count exceeds the frozen limit")
    total_bytes = 0
    for page in request.pages:
        if len(page.elements) > MAX_ELEMENTS_PER_PAGE:
            raise PptRenderingError(
                "PPT_ELEMENT_LIMIT_EXCEEDED", "page element count exceeds the frozen limit"
            )
        total_bytes += _encoded_size(page.page_key)
        for background in page.backgrounds:
            if len(background.content) > MAX_BACKGROUND_BYTES:
                raise PptRenderingError(
                    "PPT_BACKGROUND_SIZE_EXCEEDED", "background bytes exceed the frozen limit"
                )
            total_bytes += len(background.content) + _encoded_size(background.media_type)
        for element in page.elements:
            total_bytes += _encoded_size(element.element_key) + _encoded_size(element.kind)
            if isinstance(element, TextElement):
                total_bytes += _encoded_size(element.text) + _encoded_size(element.font.family)
        if total_bytes > MAX_TOTAL_INPUT_BYTES:
            raise PptRenderingError(
                "PPT_TOTAL_INPUT_SIZE_EXCEEDED", "request bytes exceed the frozen limit"
            )


def _encoded_size(value: str) -> int:
    return len(value.encode("utf-8"))


def _validate_hash_text_encoding(request: AssemblyRequest) -> None:
    for page in request.pages:
        _validate_utf8(page.page_key)
        for background in page.backgrounds:
            _validate_utf8(background.media_type)
        for element in page.elements:
            _validate_utf8(element.element_key)
            _validate_utf8(element.kind)
            if isinstance(element, TextElement):
                _validate_utf8(element.text)
                _validate_utf8(element.font.family)
                _validate_utf8(element.font.color)
            else:
                _validate_utf8(element.line_color)
                if element.fill_color is not None:
                    _validate_utf8(element.fill_color)


def _validate_utf8(value: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PptRenderingError(
            "PPT_TEXT_ENCODING_INVALID", "identity or hashed text is not valid UTF-8"
        ) from exc


def _validate_xml_text(value: str) -> None:
    _validate_utf8(value)
    for character in value:
        codepoint = ord(character)
        if codepoint in {0x09, 0x0A, 0x0D}:
            continue
        if 0x20 <= codepoint <= 0xD7FF or 0xE000 <= codepoint <= 0xFFFD:
            continue
        if 0x10000 <= codepoint <= 0x10FFFF:
            continue
        raise PptRenderingError(
            "PPT_XML_TEXT_INVALID", "text contains a character forbidden by XML 1.0"
        )
