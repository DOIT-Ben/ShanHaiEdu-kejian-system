"""Published context-source registry owned by the artifact boundary."""

from __future__ import annotations

from workflow.context_sources import (
    ARTIFACT_CONTRACT_REGISTRY,
    CONTEXT_SOURCE_REGISTRY,
    ContextSourceDefinition,
)


def artifact_types_for_context_source(source: str) -> tuple[str, ...] | None:
    """Return the registered artifact projection for a published source."""

    definition = resolve_artifact_source(source)
    if definition is None:
        return None
    return definition.artifact_types


def resolve_artifact_source(source: str) -> ContextSourceDefinition | None:
    """Resolve only explicitly published artifact source or input-contract keys."""

    definition = CONTEXT_SOURCE_REGISTRY.get(source)
    if definition is None:
        definition = ARTIFACT_CONTRACT_REGISTRY.get(source)
    if definition is None:
        definition = next(
            (
                candidate
                for candidate in CONTEXT_SOURCE_REGISTRY.values()
                if candidate.contract_ref == source
            ),
            None,
        )
    return definition if definition is not None and definition.resolver_kind == "artifact" else None


def is_known_context_source(source: str) -> bool:
    return (
        source in CONTEXT_SOURCE_REGISTRY
        or source in ARTIFACT_CONTRACT_REGISTRY
        or any(candidate.contract_ref == source for candidate in CONTEXT_SOURCE_REGISTRY.values())
    )
