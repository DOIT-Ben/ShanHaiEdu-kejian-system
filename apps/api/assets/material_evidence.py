"""Read evidence identities from current material-parse content shapes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast


def material_evidence_keys(content: Mapping[str, Any] | None) -> set[str]:
    if content is None:
        return set()
    keys = _keys(content.get("material_evidence"), "evidence_key")
    for page in _mappings(content.get("pages")):
        keys.update(_keys(page.get("text_blocks"), "block_id"))
        keys.update(_keys(page.get("image_references"), "image_id"))
    return keys


def _keys(value: object, key_name: str) -> set[str]:
    return {
        key
        for item in _mappings(value)
        if isinstance((key := item.get(key_name)), str) and key.strip()
    }


def _mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(
        cast(Mapping[str, Any], item)
        for item in cast(Sequence[object], value)
        if isinstance(item, Mapping)
    )
