"""Published context-source registry owned by the artifact boundary."""

from __future__ import annotations

from workflow.context_sources import CONTEXT_SOURCE_REGISTRY


def artifact_types_for_context_source(source: str) -> tuple[str, ...] | None:
    """Return the registered artifact projection for a published source."""

    definition = CONTEXT_SOURCE_REGISTRY.get(source)
    if definition is None or definition.resolver_kind != "artifact":
        return None
    return definition.artifact_types
