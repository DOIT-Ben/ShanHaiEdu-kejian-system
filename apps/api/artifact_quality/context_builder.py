"""Pure assembly of immutable artifact-quality validation context."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from apps.api.artifact_quality.binding import QualityReportBinding
from apps.api.artifact_quality.contracts import (
    ArtifactQualityReportResult,
    QualitySource,
    QualityValidationContext,
)
from apps.api.runtime_boundary.ports import WorkflowExecutionContext


def build_quality_validation_context(
    execution: WorkflowExecutionContext,
    source: QualitySource,
    binding: QualityReportBinding,
    supporting_inputs: dict[str, dict[str, Any]],
    supporting_versions: dict[str, UUID],
    existing_result: ArtifactQualityReportResult | None,
) -> QualityValidationContext:
    return QualityValidationContext(
        organization_id=execution.organization_id,
        project_id=execution.project_id,
        lesson_unit_id=execution.lesson_unit_id,
        content_release_id=execution.content_release_id,
        workflow_definition_version_id=execution.workflow_definition_version_id,
        node_run_id=execution.node_run_id,
        source_type=source.source_type,
        source_id=source.source_id,
        source_version_id=source.source_version_id,
        source_content_hash=source.content_hash,
        source_content=source.content,
        source_schema=source.schema or {},
        validator_refs=binding.validator_refs,
        validator_set_hash=binding.validator_set_hash,
        lesson_key=execution.lesson_key,
        supporting_inputs=supporting_inputs,
        supporting_input_versions=supporting_versions,
        existing_result=existing_result,
    )
