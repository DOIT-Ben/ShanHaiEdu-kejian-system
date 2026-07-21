from __future__ import annotations

from typing import Literal

import pytest

from apps.api.ppt_rendering import (
    MAX_BACKGROUND_BYTES,
    MAX_ELEMENTS_PER_PAGE,
    MAX_PAGES,
    MAX_TOTAL_INPUT_BYTES,
    SUPPORTED_BACKGROUND_MEDIA_TYPES,
    AssemblyRequest,
    BackgroundImage,
    Box,
    CanvasSpec,
    PptRenderingError,
    ShapeElement,
    TextElement,
    assemble_pages,
)
from tests.unit.ppt_rendering.helpers import (
    indexed_png_bytes,
    insert_png_chunks,
    jpeg_bytes,
    make_page,
    make_request,
    png_bytes,
)


@pytest.mark.parametrize(
    ("backgrounds", "code"),
    [
        ((), "PPT_PAGE_BACKGROUND_REQUIRED"),
        (
            (
                BackgroundImage(content=png_bytes(), media_type="image/png"),
                BackgroundImage(content=png_bytes(red=10), media_type="image/png"),
            ),
            "PPT_PAGE_BACKGROUND_MULTIPLE",
        ),
    ],
)
def test_each_page_requires_exactly_one_background(
    backgrounds: tuple[BackgroundImage, ...], code: str
) -> None:
    page = make_page().model_copy(update={"backgrounds": backgrounds})

    with pytest.raises(PptRenderingError, match=code) as caught:
        assemble_pages(make_request(pages=(page,)))

    assert caught.value.code == code


@pytest.mark.parametrize(
    ("render_request", "code"),
    [
        (
            make_request(
                pages=(
                    make_page(page_key="same", position=1),
                    make_page(page_key="same", position=2),
                )
            ),
            "PPT_PAGE_KEY_DUPLICATE",
        ),
        (
            make_request(pages=(make_page(page_key="page-2", position=2),)),
            "PPT_PAGE_ORDER_INVALID",
        ),
        (
            AssemblyRequest(
                canvas=CanvasSpec.model_construct(width=12_192_000, height=7_315_200),
                pages=(make_page(),),
            ),
            "PPT_CANVAS_ASPECT_RATIO_INVALID",
        ),
    ],
)
def test_request_identity_and_canvas_fail_closed(
    render_request: AssemblyRequest, code: str
) -> None:
    with pytest.raises(PptRenderingError, match=code) as caught:
        assemble_pages(render_request)

    assert caught.value.code == code


def test_missing_page_key_has_stable_error() -> None:
    page = make_page().model_copy(update={"page_key": ""})

    with pytest.raises(PptRenderingError, match="PPT_PAGE_KEY_REQUIRED") as caught:
        assemble_pages(make_request(pages=(page,)))

    assert caught.value.code == "PPT_PAGE_KEY_REQUIRED"


def test_element_outside_safe_area_is_rejected() -> None:
    source = make_page()
    overflowing = TextElement(
        element_key="outside",
        kind="annotation",
        text="越界",
        box=Box(x=12_000_000, y=500_000, width=1_000_000, height=500_000),
    )
    page = source.model_copy(update={"elements": (*source.elements, overflowing)})

    with pytest.raises(PptRenderingError, match="PPT_ELEMENT_OUT_OF_BOUNDS") as caught:
        assemble_pages(make_request(pages=(page,)))

    assert caught.value.code == "PPT_ELEMENT_OUT_OF_BOUNDS"


def test_duplicate_element_keys_are_rejected() -> None:
    source = make_page()
    duplicate = source.elements[0].model_copy(update={"text": "重复对象"})
    page = source.model_copy(update={"elements": (*source.elements, duplicate)})

    with pytest.raises(PptRenderingError, match="PPT_ELEMENT_KEY_DUPLICATE"):
        assemble_pages(make_request(pages=(page,)))


@pytest.mark.parametrize(
    ("content", "media_type", "code"),
    [
        (png_bytes()[:-1], "image/png", "PPT_BACKGROUND_IMAGE_INVALID"),
        (jpeg_bytes()[:-1], "image/jpeg", "PPT_BACKGROUND_IMAGE_PROFILE_UNSUPPORTED"),
        (png_bytes(), "image/jpeg", "PPT_BACKGROUND_IMAGE_PROFILE_UNSUPPORTED"),
        (png_bytes(width=2, height=2), "image/png", "PPT_BACKGROUND_ASPECT_RATIO_INVALID"),
    ],
)
def test_background_image_integrity_and_aspect_ratio_fail_closed(
    content: bytes, media_type: str, code: str
) -> None:
    background = BackgroundImage.model_construct(content=content, media_type=media_type)
    page = make_page().model_copy(update={"backgrounds": (background,)})

    with pytest.raises(PptRenderingError, match=code) as caught:
        assemble_pages(make_request(pages=(page,)))

    assert caught.value.code == code


def test_valid_png_dimensions_are_recorded() -> None:
    background = BackgroundImage(content=png_bytes(), media_type="image/png")
    page = make_page().model_copy(update={"backgrounds": (background,)})

    manifest = assemble_pages(make_request(pages=(page,)))

    assert manifest.pages[0].background_width == 160
    assert manifest.pages[0].background_height == 90


def test_png_crc_corruption_is_rejected() -> None:
    corrupted = bytearray(png_bytes())
    corrupted[-1] ^= 0x01
    background = BackgroundImage(content=bytes(corrupted), media_type="image/png")
    page = make_page().model_copy(update={"backgrounds": (background,)})

    with pytest.raises(PptRenderingError, match="PPT_BACKGROUND_IMAGE_INVALID"):
        assemble_pages(make_request(pages=(page,)))


@pytest.mark.parametrize("chunk_kind", [b"a1aa", b"abca"])
def test_png_chunk_type_and_reserved_bit_are_validated(chunk_kind: bytes) -> None:
    content = insert_png_chunks(png_bytes(), before_kind=b"IDAT", chunks=((chunk_kind, b""),))
    background = BackgroundImage(content=content, media_type="image/png")
    page = make_page().model_copy(update={"backgrounds": (background,)})

    with pytest.raises(PptRenderingError, match="PPT_BACKGROUND_IMAGE_INVALID"):
        assemble_pages(make_request(pages=(page,)))


@pytest.mark.parametrize(
    "content",
    [
        insert_png_chunks(
            png_bytes(), before_kind=b"IDAT", chunks=((b"gAMA", b"\x00\x00\xb1\x8f"),)
        ),
        insert_png_chunks(
            png_bytes(),
            before_kind=b"IDAT",
            chunks=((b"gAMA", b"\x00\x00\xb1\x8f"), (b"gAMA", b"\x00\x00\xb1\x8f")),
        ),
        insert_png_chunks(
            png_bytes(), before_kind=b"IDAT", chunks=((b"sRGB", b"\x00"), (b"sRGB", b"\x00"))
        ),
        insert_png_chunks(png_bytes(), before_kind=b"IDAT", chunks=((b"gAMA", b"\x01"),)),
        insert_png_chunks(
            png_bytes(), before_kind=b"IEND", chunks=((b"gAMA", b"\x00\x00\xb1\x8f"),)
        ),
    ],
)
def test_png_v1_profile_rejects_unlisted_ancillary_chunks(content: bytes) -> None:
    background = BackgroundImage(content=content, media_type="image/png")
    page = make_page().model_copy(update={"backgrounds": (background,)})

    with pytest.raises(PptRenderingError, match="PPT_BACKGROUND_IMAGE_INVALID"):
        assemble_pages(make_request(pages=(page,)))


def test_png_rejects_duplicate_transparency_singleton() -> None:
    content = insert_png_chunks(
        indexed_png_bytes(),
        before_kind=b"IDAT",
        chunks=((b"tRNS", b"\xff"), (b"tRNS", b"\xff")),
    )
    background = BackgroundImage(content=content, media_type="image/png")
    page = make_page().model_copy(update={"backgrounds": (background,)})

    with pytest.raises(PptRenderingError, match="PPT_BACKGROUND_IMAGE_INVALID"):
        assemble_pages(make_request(pages=(page,)))


@pytest.mark.parametrize(
    "content",
    [
        insert_png_chunks(
            indexed_png_bytes(),
            before_kind=b"IDAT",
            chunks=((b"PLTE", bytes((0, 0, 0))),),
        ),
        insert_png_chunks(indexed_png_bytes(), before_kind=b"PLTE", chunks=((b"tRNS", b"\xff"),)),
        insert_png_chunks(
            indexed_png_bytes(),
            before_kind=b"IEND",
            chunks=((b"PLTE", bytes((0, 0, 0))),),
        ),
        insert_png_chunks(indexed_png_bytes(), before_kind=b"IEND", chunks=((b"tRNS", b"\xff"),)),
        insert_png_chunks(indexed_png_bytes(), before_kind=b"IEND", chunks=((b"IEND", b""),)),
        insert_png_chunks(
            png_bytes(),
            before_kind=b"IDAT",
            chunks=(
                (b"tRNS", b"\x00\xf5\x00\xf8\x00\xff"),
                (b"PLTE", bytes((0, 0, 0))),
            ),
        ),
    ],
)
def test_png_rejects_duplicate_singletons_and_illegal_chunk_order(content: bytes) -> None:
    background = BackgroundImage(content=content, media_type="image/png")
    page = make_page().model_copy(update={"backgrounds": (background,)})

    with pytest.raises(PptRenderingError, match="PPT_BACKGROUND_IMAGE_INVALID"):
        assemble_pages(make_request(pages=(page,)))


@pytest.mark.parametrize(
    "content",
    [
        insert_png_chunks(
            indexed_png_bytes(), before_kind=b"IDAT", chunks=((b"tRNS", b"\xff\x80"),)
        ),
        insert_png_chunks(
            png_bytes(),
            before_kind=b"IDAT",
            chunks=((b"tRNS", b"\x00\xf5\x00\xf8\x00\xff"),),
        ),
    ],
)
def test_png_accepts_valid_transparency_chunks(content: bytes) -> None:
    background = BackgroundImage(content=content, media_type="image/png")
    page = make_page().model_copy(update={"backgrounds": (background,)})

    manifest = assemble_pages(make_request(pages=(page,)))

    assert manifest.pages[0].background_width == 160


def test_valid_indexed_color_png_is_accepted() -> None:
    background = BackgroundImage(content=indexed_png_bytes(), media_type="image/png")
    page = make_page().model_copy(update={"backgrounds": (background,)})

    manifest = assemble_pages(make_request(pages=(page,)))

    assert manifest.pages[0].background_width == 160
    assert manifest.pages[0].background_height == 90


def test_indexed_color_png_rejects_palette_index_out_of_range() -> None:
    background = BackgroundImage(content=indexed_png_bytes(pixel_index=2), media_type="image/png")
    page = make_page().model_copy(update={"backgrounds": (background,)})

    with pytest.raises(PptRenderingError, match="PPT_BACKGROUND_IMAGE_INVALID"):
        assemble_pages(make_request(pages=(page,)))


def test_all_jpeg_profiles_are_stably_unsupported() -> None:
    assert SUPPORTED_BACKGROUND_MEDIA_TYPES == ("image/png",)
    forged = b"\xff\xd8\xff\xc0\x00\x08\x08\x00\x5a\x00\xa0\x00\xff\xda\x00\x02\xff\xd9"
    for content in (jpeg_bytes(), forged):
        background = BackgroundImage(content=content, media_type="image/jpeg")
        page = make_page().model_copy(update={"backgrounds": (background,)})

        with pytest.raises(
            PptRenderingError, match="PPT_BACKGROUND_IMAGE_PROFILE_UNSUPPORTED"
        ) as caught:
            assemble_pages(make_request(pages=(page,)))

        assert caught.value.code == "PPT_BACKGROUND_IMAGE_PROFILE_UNSUPPORTED"


@pytest.mark.parametrize("kind", ["line", "arrow"])
def test_line_and_arrow_reject_unused_fill_semantics(kind: Literal["line", "arrow"]) -> None:
    source = make_page()
    shape = ShapeElement(
        element_key=kind,
        kind=kind,
        box=source.elements[-1].box,
        fill_color="FFD966",
        line_color="C55A11",
    )
    page = source.model_copy(update={"elements": (shape,)})

    with pytest.raises(PptRenderingError, match="PPT_SHAPE_FILL_UNSUPPORTED") as caught:
        assemble_pages(make_request(pages=(page,)))

    assert caught.value.code == "PPT_SHAPE_FILL_UNSUPPORTED"


def test_page_key_lone_surrogate_has_stable_domain_error() -> None:
    page = make_page().model_copy(update={"page_key": "page-\ud800"})

    with pytest.raises(PptRenderingError, match="PPT_TEXT_ENCODING_INVALID") as caught:
        assemble_pages(make_request(pages=(page,)))

    assert caught.value.code == "PPT_TEXT_ENCODING_INVALID"


@pytest.mark.parametrize(
    ("update", "code"),
    [
        ({"element_key": "invalid\x00name"}, "PPT_XML_TEXT_INVALID"),
        ({"text": "invalid\x01text"}, "PPT_XML_TEXT_INVALID"),
        ({"font": {"family": "invalid\ud800font"}}, "PPT_TEXT_ENCODING_INVALID"),
    ],
)
def test_xml_10_illegal_characters_are_rejected(update: dict[str, object], code: str) -> None:
    source = make_page()
    title = source.elements[0]
    if "font" in update:
        font = title.font.model_copy(update=update["font"])  # type: ignore[union-attr]
        update = {"font": font}
    invalid = title.model_copy(update=update)
    page = source.model_copy(update={"elements": (invalid, *source.elements[1:])})

    with pytest.raises(PptRenderingError, match=code):
        assemble_pages(make_request(pages=(page,)))


def test_request_size_limits_are_stable() -> None:
    too_many_pages = tuple(
        make_page(page_key=f"page-{position}", position=position)
        for position in range(1, MAX_PAGES + 2)
    )
    with pytest.raises(PptRenderingError, match="PPT_PAGE_LIMIT_EXCEEDED"):
        assemble_pages(make_request(pages=too_many_pages))

    source = make_page()
    too_many_elements = tuple(
        source.elements[0].model_copy(update={"element_key": f"element-{index}"})
        for index in range(MAX_ELEMENTS_PER_PAGE + 1)
    )
    page = source.model_copy(update={"elements": too_many_elements})
    with pytest.raises(PptRenderingError, match="PPT_ELEMENT_LIMIT_EXCEEDED"):
        assemble_pages(make_request(pages=(page,)))

    oversized_content = b"x" * (MAX_BACKGROUND_BYTES + 1)
    oversized = BackgroundImage.model_construct(content=oversized_content, media_type="image/png")
    page = source.model_copy(update={"backgrounds": (oversized,)})
    with pytest.raises(PptRenderingError, match="PPT_BACKGROUND_SIZE_EXCEEDED"):
        assemble_pages(make_request(pages=(page,)))

    shared_content = b"x" * MAX_BACKGROUND_BYTES
    shared = BackgroundImage.model_construct(content=shared_content, media_type="image/png")
    page_count = MAX_TOTAL_INPUT_BYTES // MAX_BACKGROUND_BYTES + 1
    pages = tuple(
        make_page(page_key=f"page-{position}", position=position).model_copy(
            update={"backgrounds": (shared,)}
        )
        for position in range(1, page_count + 1)
    )
    with pytest.raises(PptRenderingError, match="PPT_TOTAL_INPUT_SIZE_EXCEEDED"):
        assemble_pages(make_request(pages=pages))
