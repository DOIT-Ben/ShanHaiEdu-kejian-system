"""Fail-closed validation and canonical manifest construction."""

from __future__ import annotations

import hashlib
import json
import re

from apps.api.ppt_rendering.errors import PptRenderingError
from apps.api.ppt_rendering.models import (
    IMPLEMENTATION_VERSION,
    SLIDE_HEIGHT_EMU,
    SLIDE_WIDTH_EMU,
    AssemblyManifest,
    AssemblyRequest,
    BackgroundImage,
    ManifestElement,
    ManifestPage,
    PageSpec,
    ShapeElement,
    TextElement,
)

_COLOR = re.compile(r"^[0-9A-F]{6}$")


def build_manifest(request: AssemblyRequest) -> AssemblyManifest:
    _validate_request(request)
    pages = tuple(_manifest_page(page) for page in request.pages)
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


def _validate_request(request: AssemblyRequest) -> None:
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
        _validate_page(request, page)


def _validate_page(request: AssemblyRequest, page: PageSpec) -> None:
    backgrounds = page.backgrounds
    if not backgrounds:
        raise PptRenderingError("PPT_PAGE_BACKGROUND_REQUIRED", "each page needs one background")
    if len(backgrounds) > 1:
        raise PptRenderingError("PPT_PAGE_BACKGROUND_MULTIPLE", "each page allows one background")
    for background in backgrounds:
        _validate_background(background)

    element_keys: set[str] = set()
    for element in page.elements:
        if element.element_key in element_keys:
            raise PptRenderingError("PPT_ELEMENT_KEY_DUPLICATE", "element keys must be unique")
        element_keys.add(element.element_key)
        _validate_element(request, element)


def _validate_background(background: BackgroundImage) -> None:
    signatures = {
        "image/png": b"\x89PNG\r\n\x1a\n",
        "image/jpeg": b"\xff\xd8\xff",
    }
    if not background.content.startswith(signatures[background.media_type]):
        raise PptRenderingError(
            "PPT_BACKGROUND_MEDIA_INVALID", "background bytes do not match media type"
        )


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
    if isinstance(element, TextElement):
        if not element.text.strip():
            raise PptRenderingError("PPT_TEXT_REQUIRED", "text elements cannot be blank")
        if not _COLOR.fullmatch(element.font.color):
            raise PptRenderingError("PPT_COLOR_INVALID", "font color must be six hex digits")
    elif not _COLOR.fullmatch(element.line_color) or (
        element.fill_color is not None and not _COLOR.fullmatch(element.fill_color)
    ):
        raise PptRenderingError("PPT_COLOR_INVALID", "shape colors must be six hex digits")


def _manifest_page(page: PageSpec) -> ManifestPage:
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
        )
        for element in page.elements
    )
    return ManifestPage(
        page_key=page.page_key,
        position=page.position,
        background_sha256=hashlib.sha256(background.content).hexdigest(),
        background_media_type=background.media_type,
        background_size_bytes=len(background.content),
        elements=elements,
    )
