from __future__ import annotations

from apps.api.artifacts.context_source_registry import resolve_artifact_source
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


def test_selected_video_clips_are_not_resolved_as_candidate_artifacts() -> None:
    definition = CONTEXT_SOURCE_REGISTRY["video.clips.approved_versions"]

    assert definition.resolver_kind == "asset"
    assert definition.contract_ref == "asset:video_selected_clips"
    assert definition.artifact_types == ()
    assert resolve_artifact_source("video.clips.approved_versions") is None
