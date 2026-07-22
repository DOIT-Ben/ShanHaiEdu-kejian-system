"""Resolve an exact quality-report source through its owning module port."""

from __future__ import annotations

from apps.api.artifact_quality.binding import QualityReportBinding
from apps.api.artifact_quality.contracts import QualitySource
from apps.api.artifacts.quality_port import SqlAlchemyArtifactQualitySourcePort
from apps.api.assets.quality_port import SqlAlchemyAssetQualitySourcePort
from apps.api.runtime_boundary.ports import WorkflowExecutionContext
from apps.api.workflows.quality_port import QualitySourceInput


def resolve_quality_source(
    execution: WorkflowExecutionContext,
    binding: QualityReportBinding,
    source_input: QualitySourceInput,
    artifacts: SqlAlchemyArtifactQualitySourcePort,
    assets: SqlAlchemyAssetQualitySourcePort,
) -> QualitySource:
    if source_input.source_type == "artifact":
        return artifacts.load(
            execution,
            contract_ref=binding.source_input_ref,
            source_id=source_input.source_id,
            source_version_id=source_input.source_version_id,
        )
    if source_input.source_type == "asset":
        return assets.load(
            execution,
            contract_ref=binding.source_input_ref,
            source_id=source_input.source_id,
            source_version_id=source_input.source_version_id,
        )
    raise QualitySourceResolutionError(
        "QUALITY_SOURCE_TYPE_UNSUPPORTED",
        "the fixed quality source type is unsupported",
    )


class QualitySourceResolutionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
