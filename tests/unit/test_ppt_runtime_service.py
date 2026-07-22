from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import cast
from uuid import UUID

import pytest

from apps.api.assets.ppt_runtime_contracts import PptBackgroundFact, PublishedPptxObject
from apps.api.ppt_rendering.models import AssemblyRequest, ManifestPage
from apps.api.ppt_rendering.service import assemble_pages
from apps.api.ppt_runtime.contracts import (
    PptRenderProduct,
    PptRuntimeError,
    PptRuntimeResult,
    PptRuntimeTransaction,
    PreparedPptRuntime,
)
from apps.api.ppt_runtime.outputs import merge_page_manifests
from apps.api.ppt_runtime.page_recovery import (
    build_page_recovery_details,
    parse_page_recovery_details,
)
from apps.api.ppt_runtime.service import PptRuntimeService
from tests.fakes.object_storage import FakeObjectStorage
from tests.unit.ppt_rendering.helpers import make_page, make_request


class _PrepareFailureTransaction:
    def prepare(
        self,
        node_run_id: UUID,
        request_id: str,
    ) -> PreparedPptRuntime | PptRuntimeResult:
        raise PptRuntimeError("PPT_RUNTIME_BINDING_INVALID", "invalid binding")

    def complete(
        self,
        prepared: PreparedPptRuntime,
        product: PptRenderProduct,
        published: PublishedPptxObject | None,
        *,
        latency_ms: int,
    ) -> PptRuntimeResult:
        raise AssertionError("complete must not run")

    def terminalize_failure(
        self,
        prepared: PreparedPptRuntime,
        *,
        code: str,
        cancelled: bool,
        latency_ms: int,
        completed_pages: tuple[ManifestPage, ...],
    ) -> None:
        raise AssertionError("terminalize_failure must not run")

    def fail_prepare(self, node_run_id: UUID, *, code: str) -> None:
        raise RuntimeError("injected prepare terminalization failure")


class _PrepareFailureFactory:
    @contextmanager
    def begin(self) -> Generator[PptRuntimeTransaction]:
        yield _PrepareFailureTransaction()


def test_page_manifest_merge_matches_frozen_whole_request_hash() -> None:
    request = make_request(
        pages=tuple(
            make_page(page_key=f"PAGE-{index:02d}", position=index) for index in range(1, 6)
        )
    )
    expected = assemble_pages(request)
    pages: list[ManifestPage] = []
    for page in request.pages:
        single = AssemblyRequest(
            canvas=request.canvas,
            pages=(page.model_copy(update={"position": 1}),),
        )
        rendered = assemble_pages(single).pages[0]
        pages.append(rendered.model_copy(update={"position": page.position}))

    assert merge_page_manifests(request.canvas, tuple(pages)) == expected


def test_prepare_failure_reports_terminalization_failure() -> None:
    service = PptRuntimeService(
        _PrepareFailureFactory(),
        FakeObjectStorage(),
        storage_bucket="shanhaiedu",
    )

    with pytest.raises(PptRuntimeError) as caught:
        service.execute(
            UUID("01900000-0000-7000-8000-000000000170"),
            request_id="issue-170-prepare-failure",
        )

    assert caught.value.code == "PPT_RUNTIME_FAILURE_COMMIT_FAILED"


def test_recovery_rejects_tampered_page_facts() -> None:
    pages, backgrounds = _recovery_facts()
    request_hash = "a" * 64
    details = build_page_recovery_details(pages[:2], request_hash=request_hash)
    raw_pages = cast(list[object], details["completed_pages"])
    first_page = cast(dict[str, object], raw_pages[0])
    raw_elements = cast(list[object], first_page["elements"])
    first_element = cast(dict[str, object], raw_elements[0])
    first_element["text"] = "tampered recovered text"

    with pytest.raises(PptRuntimeError) as caught:
        parse_page_recovery_details(
            details,
            backgrounds=backgrounds,
            request_hash=request_hash,
        )

    assert caught.value.code == "PPT_RUNTIME_PAGE_RECOVERY_INVALID"


def test_recovery_rejects_wrong_request_hash() -> None:
    pages, backgrounds = _recovery_facts()
    details = build_page_recovery_details(pages[:2], request_hash="a" * 64)
    details["request_hash"] = "b" * 64

    with pytest.raises(PptRuntimeError) as caught:
        parse_page_recovery_details(
            details,
            backgrounds=backgrounds,
            request_hash="a" * 64,
        )

    assert caught.value.code == "PPT_RUNTIME_PAGE_RECOVERY_INVALID"


def test_recovery_rejects_non_prefix_pages() -> None:
    pages, backgrounds = _recovery_facts()
    details = build_page_recovery_details(
        (pages[0], pages[2]),
        request_hash="a" * 64,
    )

    with pytest.raises(PptRuntimeError) as caught:
        parse_page_recovery_details(
            details,
            backgrounds=backgrounds,
            request_hash="a" * 64,
        )

    assert caught.value.code == "PPT_RUNTIME_PAGE_RECOVERY_INVALID"


def _recovery_facts() -> tuple[tuple[ManifestPage, ...], tuple[PptBackgroundFact, ...]]:
    request = make_request(
        pages=tuple(
            make_page(page_key=f"PAGE-{index:02d}", position=index) for index in range(1, 4)
        )
    )
    pages = assemble_pages(request).pages
    backgrounds = tuple(
        PptBackgroundFact(
            page_key=page.page_key,
            position=page.position,
            slot_key=f"ppt.background.{page.page_key}",
            binding_id=UUID(int=index),
            file_asset_id=UUID(int=10 + index),
            file_asset_version_id=UUID(int=20 + index),
            storage_bucket="shanhaiedu",
            storage_key=f"backgrounds/{page.page_key}.png",
            mime_type=page.background_media_type,
            size_bytes=page.background_size_bytes,
            sha256=page.background_sha256,
            width=page.background_width,
            height=page.background_height,
        )
        for index, page in enumerate(pages, start=1)
    )
    return pages, backgrounds
