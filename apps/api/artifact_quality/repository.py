"""Tenant-scoped exact queries for immutable artifact quality reports."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifact_quality.contracts import QualitySourceType
from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService


class ArtifactQualityReportRepository:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def get_for_node(self, node_run_id: UUID) -> ArtifactQualityReport | None:
        return self._session.scalar(
            select(ArtifactQualityReport).where(
                ArtifactQualityReport.organization_id == self._actor.organization_id,
                ArtifactQualityReport.validate_node_run_id == node_run_id,
            )
        )

    def get_exact(
        self,
        *,
        project_id: UUID,
        source_type: QualitySourceType,
        source_version_id: UUID,
        workflow_definition_version_id: UUID,
        validator_set_hash: str,
    ) -> ArtifactQualityReport | None:
        if not self._actor.is_system:
            ProjectAccessService(self._session, self._actor).require(
                project_id,
                ProjectAction.VIEW,
            )
        source_column = (
            ArtifactQualityReport.source_artifact_version_id
            if source_type == "artifact"
            else ArtifactQualityReport.source_file_asset_version_id
        )
        return self._session.scalar(
            select(ArtifactQualityReport).where(
                ArtifactQualityReport.organization_id == self._actor.organization_id,
                ArtifactQualityReport.project_id == project_id,
                ArtifactQualityReport.source_type == source_type,
                source_column == source_version_id,
                ArtifactQualityReport.workflow_definition_version_id
                == workflow_definition_version_id,
                ArtifactQualityReport.validator_set_hash == validator_set_hash,
            )
        )
