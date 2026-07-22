"""Artifact-owned exact source adapter for quality validation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifact_quality.contracts import QualitySource
from apps.api.artifacts.context_source_registry import resolve_artifact_source
from apps.api.artifacts.execution_errors import ArtifactExecutionPortError
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.content_runtime.approval_port import ContentDefinitionApprovalReader
from apps.api.identity.context import ActorContext
from apps.api.runtime_boundary.ports import WorkflowExecutionContext


class SqlAlchemyArtifactQualitySourcePort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def load(
        self,
        execution: WorkflowExecutionContext,
        *,
        contract_ref: str,
        source_id: UUID,
        source_version_id: UUID,
    ) -> QualitySource:
        definition = resolve_artifact_source(contract_ref)
        if definition is None:
            raise ArtifactExecutionPortError(
                "QUALITY_SOURCE_CONTRACT_UNKNOWN",
                "the quality artifact source contract is not registered",
            )
        statement = (
            select(ArtifactVersion, Artifact)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                ArtifactVersion.id == source_version_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                Artifact.id == source_id,
                Artifact.organization_id == self._actor.organization_id,
                Artifact.project_id == execution.project_id,
                Artifact.deleted_at.is_(None),
                (
                    Artifact.lesson_unit_id == execution.lesson_unit_id
                    if definition.scope == "lesson"
                    else Artifact.lesson_unit_id.is_(None)
                ),
                Artifact.branch_key == definition.branch_key,
                Artifact.artifact_type.in_(definition.artifact_types),
            )
        )
        if definition.requires_current_approval:
            statement = statement.where(
                Artifact.current_approved_version_id == source_version_id,
                Artifact.status == "approved",
            )
        row = self._session.execute(statement).one_or_none()
        if row is None:
            raise _scope_invalid("the exact artifact source is unavailable in the fixed scope")
        version, artifact = row
        content_definition = ContentDefinitionApprovalReader(self._session).definition_fact(
            definition_id=artifact.content_definition_version_id,
            content_release_id=execution.content_release_id,
        )
        if content_definition is None:
            raise _scope_invalid("the artifact definition is unavailable in the fixed release")
        return QualitySource(
            source_type="artifact",
            source_id=artifact.id,
            source_version_id=version.id,
            content_hash=version.content_hash,
            content=version.content_json,
            schema=content_definition.schema,
        )


def _scope_invalid(message: str) -> ArtifactExecutionPortError:
    return ArtifactExecutionPortError("QUALITY_SOURCE_SCOPE_INVALID", message)
