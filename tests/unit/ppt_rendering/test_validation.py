from __future__ import annotations

import pytest

from apps.api.ppt_rendering import (
    AssemblyRequest,
    BackgroundImage,
    Box,
    CanvasSpec,
    PptRenderingError,
    TextElement,
    assemble_pages,
)
from tests.unit.ppt_rendering.helpers import make_page, make_request, png_bytes


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
