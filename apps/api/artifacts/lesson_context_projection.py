"""Artifact-owned projections for lesson-scoped workflow context."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any, cast

_LESSON_DIVISION_SOURCES = frozenset(
    {
        "lesson_division.approved_version",
        "approval:lesson_division",
    }
)


class LessonContextProjectionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def project_artifact_context(
    *,
    source: str,
    lesson_key: str | None,
    content: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the exact lesson view for declared project-scoped lesson inputs."""

    if source not in _LESSON_DIVISION_SOURCES or lesson_key is None:
        return deepcopy(dict(content))
    raw_units = content.get("lesson_units")
    if not isinstance(raw_units, Sequence) or isinstance(raw_units, (str, bytes, bytearray)):
        raise _invalid()
    matches = [
        cast(Mapping[str, Any], raw)
        for raw in cast(Sequence[object], raw_units)
        if isinstance(raw, Mapping)
        and cast(Mapping[str, Any], raw).get("lesson_unit_key") == lesson_key
    ]
    division_key = content.get("division_key")
    if len(matches) != 1 or type(division_key) is not str or not division_key.strip():
        raise _invalid()
    return {
        "division_key": division_key,
        "lesson_unit": deepcopy(dict(matches[0])),
    }


def _invalid() -> LessonContextProjectionError:
    return LessonContextProjectionError(
        "NODE_EXECUTION_LESSON_SCOPE_INVALID",
        "the approved lesson division does not contain one exact target lesson",
    )
