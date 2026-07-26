"""Identity checks for the three-category, nine-option quality contract."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def default_nine_identity_findings(
    options: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    prefixes = {
        "science": "INTRO-SCI-",
        "application": "INTRO-APP-",
        "story": "INTRO-STO-",
    }
    option_keys = [option.get("option_key") for option in options]
    key_invalid = (
        any(type(key) is not str or not key.strip() for key in option_keys)
        or len(option_keys) != len(set(option_keys))
        or any(
            not isinstance(key, str)
            or not isinstance(tendency, str)
            or tendency not in prefixes
            or not key.startswith(prefixes[tendency])
            for key, tendency in (
                (option.get("option_key"), option.get("primary_tendency")) for option in options
            )
        )
    )
    findings: list[dict[str, Any]] = []
    if key_invalid:
        findings.append(
            _finding(
                "INTRO_OPTION_KEY_INVALID",
                "option keys must be unique and match their primary tendency",
            )
        )
    concepts = [
        "".join(value.split()).casefold()
        for value in (option.get("creative_concept") for option in options)
        if type(value) is str and value.strip()
    ]
    if len(concepts) == len(options) and len(concepts) != len(set(concepts)):
        findings.append(
            _finding(
                "INTRO_OPTION_CONTENT_DUPLICATED",
                "creative concepts must be distinct after normalization",
            )
        )
    return findings


def _finding(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "message": message}
