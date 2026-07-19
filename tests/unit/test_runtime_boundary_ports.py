from __future__ import annotations

from apps.api.runtime_boundary.ports import (
    ArtifactPort,
    AssetPort,
    CreationPackagePort,
    ModelInvocationPort,
    PromptSnapshotPort,
    RuntimeDefinitionReader,
    WorkflowExecutionPort,
)


def test_runtime_boundary_exposes_only_the_minimum_issue_89_ports() -> None:
    expected_methods = {
        RuntimeDefinitionReader: {"resolve"},
        WorkflowExecutionPort: {"require_context", "transition"},
        ArtifactPort: {"list_context_versions", "persist_generated"},
        AssetPort: {"list_context_items"},
        PromptSnapshotPort: {"freeze"},
        ModelInvocationPort: {"generate_text"},
        CreationPackagePort: {"publish"},
    }

    for port, methods in expected_methods.items():
        assert port.__dict__.get("_is_protocol") is True
        assert methods <= set(port.__dict__)
