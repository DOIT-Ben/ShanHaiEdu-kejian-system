"""Resolve exact supporting inputs declared by a quality-report binding."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from apps.api.artifact_quality.binding import QualityReportBinding
from apps.api.artifacts.execution_errors import ArtifactExecutionPortError
from apps.api.artifacts.quality_port import SqlAlchemyArtifactQualitySourcePort
from apps.api.assets.execution_port import AssetExecutionPortError
from apps.api.assets.quality_port import SqlAlchemyAssetQualitySourcePort
from apps.api.runtime_boundary.ports import WorkflowExecutionContext
from apps.api.workflows.quality_port import SqlAlchemyQualityWorkflowPort


def resolve_quality_supporting_inputs(
    execution: WorkflowExecutionContext,
    binding: QualityReportBinding,
    node_run_id: UUID,
    workflow: SqlAlchemyQualityWorkflowPort,
    artifacts: SqlAlchemyArtifactQualitySourcePort,
    assets: SqlAlchemyAssetQualitySourcePort,
) -> tuple[dict[str, dict[str, Any]], dict[str, UUID]]:
    resolved: dict[str, dict[str, Any]] = {}
    versions: dict[str, UUID] = {}
    for contract_ref in binding.supporting_input_refs:
        source_input = workflow.require_supporting_input(node_run_id, contract_ref)
        if source_input.source_type == "artifact":
            source = artifacts.load(
                execution,
                contract_ref=contract_ref,
                source_id=source_input.source_id,
                source_version_id=source_input.source_version_id,
            )
        elif source_input.source_type == "material_parse":
            source = assets.load_supporting(
                execution.project_id,
                contract_ref=contract_ref,
                source_id=source_input.source_id,
                source_version_id=source_input.source_version_id,
            )
        else:
            raise ArtifactExecutionPortError(
                "QUALITY_SUPPORTING_TYPE_UNSUPPORTED",
                "the frozen supporting-input type is unsupported",
            )
        if source.content_hash != source_input.content_hash:
            raise AssetExecutionPortError(
                "QUALITY_SUPPORTING_HASH_MISMATCH",
                "the frozen supporting-input hash does not match the exact source",
            )
        resolved[contract_ref] = dict(source.content)
        versions[contract_ref] = source.source_version_id
    return resolved, versions
