"""Evidence identities supported by immutable material-parse content."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast


def material_evidence_keys(material: Mapping[str, Any] | None) -> set[str]:
    if material is None:
        return set()
    return _flat_evidence_keys(material.get("material_evidence")) | _page_evidence_keys(
        material.get("pages")
    )


def _flat_evidence_keys(evidence: object) -> set[str]:
    keys: set[str] = set()
    for item in _mapping_sequence(evidence):
        key = item.get("evidence_key")
        if isinstance(key, str) and key.strip():
            keys.add(key)
    return keys


def _page_evidence_keys(pages: object) -> set[str]:
    keys: set[str] = set()
    for page in _mapping_sequence(pages):
        for collection_name, key_name in (
            ("text_blocks", "block_id"),
            ("image_references", "image_id"),
        ):
            for item in _mapping_sequence(page.get(collection_name)):
                key = item.get(key_name)
                if isinstance(key, str) and key.strip():
                    keys.add(key)
    return keys


def _mapping_sequence(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(
        cast(Mapping[str, Any], item)
        for item in cast(Sequence[object], value)
        if isinstance(item, Mapping)
    )
