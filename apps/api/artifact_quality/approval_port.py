"""Artifact-quality application facts consumed by the approval module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifact_quality.repository import ArtifactQualityReportRepository
from apps.api.identity.context import ActorContext


@dataclass(frozen=True, slots=True)
class QualityApprovalEvidence:
    report_id: UUID
    organization_id: UUID
    project_id: UUID
    lesson_unit_id: UUID | None
    source_artifact_version_id: UUID | None
    source_content_hash: str
    content_release_id: UUID
    workflow_definition_version_id: UUID
    validate_node_run_id: UUID
    validator_set: tuple[dict[str, Any], ...]
    validator_set_hash: str
    conclusion: str
    evidence_hash: str


class ArtifactQualityApprovalEvidenceReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._repository = ArtifactQualityReportRepository(session, actor)

    def find_exact(
        self,
        *,
        project_id: UUID,
        source_version_id: UUID,
        workflow_definition_version_id: UUID,
        validator_set_hash: str,
    ) -> QualityApprovalEvidence | None:
        report = self._repository.get_exact(
            project_id=project_id,
            source_type="artifact",
            source_version_id=source_version_id,
            workflow_definition_version_id=workflow_definition_version_id,
            validator_set_hash=validator_set_hash,
        )
        if report is None:
            return None
        return QualityApprovalEvidence(
            report_id=report.id,
            organization_id=report.organization_id,
            project_id=report.project_id,
            lesson_unit_id=report.lesson_unit_id,
            source_artifact_version_id=report.source_artifact_version_id,
            source_content_hash=report.source_content_hash,
            content_release_id=report.content_release_id,
            workflow_definition_version_id=report.workflow_definition_version_id,
            validate_node_run_id=report.validate_node_run_id,
            validator_set=tuple(dict(item) for item in report.validator_set_json),
            validator_set_hash=report.validator_set_hash,
            conclusion=report.conclusion,
            evidence_hash=report.evidence_hash,
        )
