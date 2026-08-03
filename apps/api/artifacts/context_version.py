"""Build projected Artifact context versions for node execution."""

from __future__ import annotations

from apps.api.artifacts.lesson_context_projection import project_artifact_context
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.runtime_boundary.ports import ArtifactContextVersion, WorkflowExecutionContext


def build_artifact_context_version(
    execution: WorkflowExecutionContext,
    contract_ref: str,
    version: ArtifactVersion,
    artifact: Artifact,
) -> ArtifactContextVersion:
    return ArtifactContextVersion(
        project_id=execution.project_id,
        lesson_unit_id=artifact.lesson_unit_id,
        artifact_version_id=version.id,
        contract_ref=contract_ref,
        artifact_type=artifact.artifact_type,
        content=project_artifact_context(
            source=contract_ref,
            lesson_key=execution.lesson_key,
            content=version.content_json,
        ),
        content_hash=version.content_hash,
    )
