"""Evidence-key projections for persisted material parse shapes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast


def material_evidence_keys(content: Mapping[str, Any]) -> set[str]:
    keys = _legacy_evidence_keys(content.get("material_evidence"))
    keys.update(_page_block_keys(content.get("pages")))
    return keys


def page_block_evidence_keys(
    content: Mapping[str, Any],
    *,
    page_start: int,
    page_end: int,
) -> tuple[str, ...]:
    pages = content.get("pages")
    if not isinstance(pages, Sequence) or isinstance(pages, (str, bytes, bytearray)):
        return ()
    keys: set[str] = set()
    selected_pages: set[int] = set()
    for item in cast(Sequence[object], pages):
        if not isinstance(item, Mapping):
            continue
        page = cast(Mapping[str, Any], item)
        page_number = page.get("page_number")
        if type(page_number) is not int or not page_start <= page_number <= page_end:
            continue
        selected_pages.add(page_number)
        keys.update(_text_block_keys(page.get("text_blocks")))
    if selected_pages != set(range(page_start, page_end + 1)):
        return ()
    return tuple(sorted(keys))


def _legacy_evidence_keys(value: object) -> set[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return set()
    keys: set[str] = set()
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            continue
        key = cast(Mapping[str, Any], item).get("evidence_key")
        if isinstance(key, str) and key.strip():
            keys.add(key)
    return keys


def _page_block_keys(value: object) -> set[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return set()
    keys: set[str] = set()
    for item in cast(Sequence[object], value):
        if isinstance(item, Mapping):
            keys.update(_text_block_keys(cast(Mapping[str, Any], item).get("text_blocks")))
    return keys


def _text_block_keys(value: object) -> set[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return set()
    keys: set[str] = set()
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            continue
        key = cast(Mapping[str, Any], item).get("block_id")
        if isinstance(key, str) and key.strip():
            keys.add(key)
    return keys
