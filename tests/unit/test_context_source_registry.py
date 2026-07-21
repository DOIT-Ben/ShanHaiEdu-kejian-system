from __future__ import annotations

from workflow.context_sources import CONTEXT_SOURCE_REGISTRY, DEFAULT_CONTEXT_SOURCES


def test_context_source_registry_is_the_single_source_of_context_keys() -> None:
    assert DEFAULT_CONTEXT_SOURCES == frozenset(CONTEXT_SOURCE_REGISTRY)
    assert all(definition.contract_ref for definition in CONTEXT_SOURCE_REGISTRY.values())
    assert all(
        definition.artifact_types
        for definition in CONTEXT_SOURCE_REGISTRY.values()
        if definition.resolver_kind == "artifact"
    )
    assert all(
        not definition.artifact_types
        for definition in CONTEXT_SOURCE_REGISTRY.values()
        if definition.resolver_kind != "artifact"
    )
