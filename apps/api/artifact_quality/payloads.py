"""Pure canonical JSON helpers for immutable quality evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, cast


def plain_json(value: Mapping[str, Any]) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)),
    )


def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
