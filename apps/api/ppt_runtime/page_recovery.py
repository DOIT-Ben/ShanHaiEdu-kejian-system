"""Bounded, tamper-evident recovery facts for deterministic PPT pages."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import cast

from apps.api.assets.ppt_runtime_contracts import PptBackgroundFact
from apps.api.ppt_rendering import ManifestPage

from .contracts import PptRuntimeError

_RECOVERY_KIND = "shanhai.ppt-page-recovery/v1"


def build_page_recovery_details(
    pages: tuple[ManifestPage, ...],
    *,
    request_hash: str,
) -> dict[str, object]:
    serialized = [page.model_dump(mode="json") for page in pages]
    return {
        "recovery_kind": _RECOVERY_KIND,
        "request_hash": request_hash,
        "completed_page_keys": [page.page_key for page in pages],
        "completed_pages": serialized,
        "completed_pages_hash": _recovery_hash(request_hash, serialized),
    }


def parse_page_recovery_details(
    details: Mapping[str, object],
    *,
    backgrounds: tuple[PptBackgroundFact, ...],
    request_hash: str,
) -> tuple[ManifestPage, ...]:
    if not details or "completed_pages" not in details:
        return ()
    raw_pages = details.get("completed_pages")
    raw_keys = details.get("completed_page_keys")
    if (
        details.get("recovery_kind") != _RECOVERY_KIND
        or details.get("request_hash") != request_hash
        or not _is_sha256(request_hash)
        or not isinstance(raw_pages, Sequence)
        or isinstance(raw_pages, (str, bytes, bytearray))
        or not isinstance(raw_keys, Sequence)
        or isinstance(raw_keys, (str, bytes, bytearray))
    ):
        raise _invalid("the deterministic page recovery facts are invalid")
    page_values = tuple(cast(Sequence[object], raw_pages))
    key_values = tuple(cast(Sequence[object], raw_keys))
    if any(type(value) is not str for value in key_values):
        raise _invalid("the deterministic page recovery order is invalid")
    try:
        pages = tuple(ManifestPage.model_validate(value) for value in page_values)
    except Exception as exc:
        raise _invalid("the deterministic page recovery facts are invalid") from exc
    serialized = [page.model_dump(mode="json") for page in pages]
    if details.get("completed_pages_hash") != _recovery_hash(request_hash, serialized):
        raise _invalid("the deterministic page recovery integrity check failed")
    keys = cast(tuple[str, ...], key_values)
    expected_prefix = backgrounds[: len(pages)]
    if (
        not pages
        or len(pages) > len(backgrounds)
        or keys != tuple(page.page_key for page in pages)
        or keys != tuple(background.page_key for background in expected_prefix)
    ):
        raise _invalid("the deterministic page recovery order is invalid")
    for page, background in zip(pages, expected_prefix, strict=True):
        if not _matches_background(page, background):
            raise _invalid("a recovered page differs from its frozen background fact")
    return pages


def _recovery_hash(request_hash: str, pages: list[dict[str, object]]) -> str:
    payload = {
        "recovery_kind": _RECOVERY_KIND,
        "request_hash": request_hash,
        "completed_pages": pages,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _matches_background(page: ManifestPage, background: PptBackgroundFact) -> bool:
    return (
        page.page_key == background.page_key
        and page.position == background.position
        and page.background_sha256 == background.sha256
        and page.background_media_type == background.mime_type
        and page.background_size_bytes == background.size_bytes
        and page.background_width == background.width
        and page.background_height == background.height
    )


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _invalid(message: str) -> PptRuntimeError:
    return PptRuntimeError("PPT_RUNTIME_PAGE_RECOVERY_INVALID", message)
