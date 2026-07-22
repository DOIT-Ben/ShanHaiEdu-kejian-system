"""Artifact-owned adapter for node execution context and writes."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.artifacts.context_source_registry import (
    is_known_context_source,
    resolve_artifact_source,
)
from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.execution_errors import ArtifactExecutionPortError
from apps.api.artifacts.generated_write_guard import GeneratedArtifactWriteGuard
from apps.api.artifacts.lesson_context_projection import project_artifact_context
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.database import utc_now
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.runtime_boundary.contract_values import plain_json_value
from apps.api.runtime_boundary.ports import (
    ArtifactContextVersion,
    ArtifactWriteResult,
    GeneratedArtifactWrite,
    WorkflowExecutionContext,
)


class SqlAlchemyArtifactPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def list_context_versions(
        self,
        execution: WorkflowExecutionContext,
        source: str,
    ) -> tuple[ArtifactContextVersion, ...]:
        ProjectAccessService(self._session, self._actor).require(
            execution.project_id,
            ProjectAction.GENERATE,
        )
        if not is_known_context_source(source):
            raise ArtifactExecutionPortError(
                "NODE_EXECUTION_CONTEXT_SOURCE_UNKNOWN",
                "the published context source is not registered",
            )
        definition = resolve_artifact_source(source)
        if definition is None:
            return ()
        if definition.scope == "lesson" and execution.lesson_unit_id is None:
            return ()
        assert definition.branch_key is not None
        rows = self._session.execute(
            select(ArtifactVersion, Artifact)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                Artifact.organization_id == self._actor.organization_id,
                Artifact.project_id == execution.project_id,
                Artifact.deleted_at.is_(None),
                Artifact.artifact_type.in_(definition.artifact_types),
                Artifact.branch_key == definition.branch_key,
                Artifact.current_approved_version_id == ArtifactVersion.id,
                ArtifactVersion.organization_id == self._actor.organization_id,
            )
            .where(
                Artifact.lesson_unit_id.is_(None)
                if definition.scope == "project"
                else Artifact.lesson_unit_id == execution.lesson_unit_id
            )
            .order_by(ArtifactVersion.created_at, ArtifactVersion.id)
        ).all()
        return tuple(
            ArtifactContextVersion(
                project_id=execution.project_id,
                lesson_unit_id=artifact.lesson_unit_id,
                artifact_version_id=version.id,
                contract_ref=source,
                artifact_type=artifact.artifact_type,
                content=project_artifact_context(
                    source=source,
                    lesson_key=execution.lesson_key,
                    content=version.content_json,
                ),
                content_hash=version.content_hash,
            )
            for version, artifact in rows
        )

    def verify_frozen_versions(
        self,
        execution: WorkflowExecutionContext,
        upstream: dict[str, ArtifactContextVersion],
    ) -> None:
        for value in upstream.values():
            definition = resolve_artifact_source(value.contract_ref)
            if definition is None:
                raise ArtifactExecutionPortError(
                    "NODE_EXECUTION_CONTEXT_SOURCE_UNKNOWN",
                    "the frozen artifact source is not registered",
                )
            row = self._session.execute(
                select(ArtifactVersion, Artifact)
                .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
                .where(
                    ArtifactVersion.id == value.artifact_version_id,
                    ArtifactVersion.organization_id == self._actor.organization_id,
                    Artifact.organization_id == self._actor.organization_id,
                    Artifact.project_id == execution.project_id,
                    Artifact.current_approved_version_id == ArtifactVersion.id,
                    Artifact.status != "stale",
                    Artifact.lesson_unit_id == value.lesson_unit_id,
                    Artifact.branch_key == definition.branch_key,
                    Artifact.artifact_type.in_(definition.artifact_types),
                    ArtifactVersion.content_hash == value.content_hash,
                )
            ).one_or_none()
            if row is None:
                raise ArtifactExecutionPortError(
                    "NODE_EXECUTION_UPSTREAM_STALE",
                    "a frozen upstream artifact is no longer the current approved version",
                )

    def load_frozen_versions(
        self,
        execution: WorkflowExecutionContext,
        refs: dict[str, UUID],
    ) -> dict[str, ArtifactContextVersion]:
        values: dict[str, ArtifactContextVersion] = {}
        for contract_ref, version_id in refs.items():
            definition = resolve_artifact_source(contract_ref)
            if definition is None:
                raise ArtifactExecutionPortError(
                    "NODE_EXECUTION_CONTEXT_SOURCE_UNKNOWN",
                    "the frozen artifact source is not registered",
                )
            row = self._session.execute(
                select(ArtifactVersion, Artifact)
                .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
                .where(
                    ArtifactVersion.id == version_id,
                    ArtifactVersion.organization_id == self._actor.organization_id,
                    Artifact.organization_id == self._actor.organization_id,
                    Artifact.project_id == execution.project_id,
                    (
                        Artifact.lesson_unit_id == execution.lesson_unit_id
                        if definition.scope == "lesson"
                        else Artifact.lesson_unit_id.is_(None)
                    ),
                    Artifact.branch_key == definition.branch_key,
                    Artifact.artifact_type.in_(definition.artifact_types),
                )
            ).one_or_none()
            if row is None:
                raise ArtifactExecutionPortError(
                    "NODE_EXECUTION_FROZEN_UPSTREAM_MISSING",
                    "a frozen upstream artifact version is unavailable",
                )
            version, artifact = row
            values[contract_ref] = ArtifactContextVersion(
                project_id=execution.project_id,
                lesson_unit_id=artifact.lesson_unit_id,
                artifact_version_id=version.id,
                contract_ref=contract_ref,
                artifact_type=artifact.artifact_type,
                content=version.content_json,
                content_hash=version.content_hash,
            )
        return values

    def persist_generated(self, write: GeneratedArtifactWrite) -> ArtifactWriteResult:
        GeneratedArtifactWriteGuard(self._session, self._actor).require(write)
        ProjectAccessService(self._session, self._actor).require(
            write.project_id,
            ProjectAction.GENERATE,
            for_update=True,
        )
        content = plain_json_value(write.content)
        if not isinstance(content, dict):
            raise ArtifactExecutionPortError(
                "NODE_EXECUTION_ARTIFACT_CONTENT_INVALID",
                "generated artifact content must be a JSON object",
            )
        typed_content = cast(dict[str, Any], content)
        content_hash = canonical_content_hash(typed_content)
        artifact = self._get_or_create_artifact(write)
        existing = self._get_or_create_version(artifact, write, typed_content, content_hash)
        self._write_relations(write, existing.id)
        return ArtifactWriteResult(
            artifact_id=artifact.id,
            artifact_version_id=existing.id,
            content_hash=existing.content_hash,
            project_id=write.project_id,
            node_run_id=write.node_run_id,
            context_snapshot_id=write.context_snapshot_id,
            prompt_snapshot_id=write.prompt_snapshot_id,
            artifact_key=artifact.artifact_key,
            artifact_type=artifact.artifact_type,
            branch_key=artifact.branch_key,
            lesson_unit_id=artifact.lesson_unit_id,
            content_definition_version_id=artifact.content_definition_version_id,
        )

    def _get_or_create_artifact(self, write: GeneratedArtifactWrite) -> Artifact:
        artifact = self._session.scalar(
            select(Artifact)
            .where(
                Artifact.organization_id == self._actor.organization_id,
                Artifact.project_id == write.project_id,
                Artifact.artifact_key == write.artifact_key,
                Artifact.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if artifact is not None:
            if (
                artifact.lesson_unit_id != write.lesson_unit_id
                or artifact.branch_key != write.branch_key
                or artifact.artifact_type != write.artifact_type
                or artifact.content_definition_version_id != write.content_definition_version_id
            ):
                raise ArtifactExecutionPortError(
                    "NODE_EXECUTION_ARTIFACT_IDENTITY_CONFLICT",
                    "the published artifact identity conflicts with the existing artifact",
                )
            return artifact
        artifact = Artifact(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=write.project_id,
            lesson_unit_id=write.lesson_unit_id,
            branch_key=write.branch_key,
            artifact_key=write.artifact_key,
            artifact_type=write.artifact_type,
            content_definition_version_id=write.content_definition_version_id,
            status="draft",
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(artifact)
        self._session.flush()
        return artifact

    def _get_or_create_version(
        self,
        artifact: Artifact,
        write: GeneratedArtifactWrite,
        content: dict[str, Any],
        content_hash: str,
    ) -> ArtifactVersion:
        existing = self._session.scalar(
            select(ArtifactVersion)
            .where(
                ArtifactVersion.organization_id == self._actor.organization_id,
                ArtifactVersion.artifact_id == artifact.id,
                ArtifactVersion.source_node_run_id == write.node_run_id,
                ArtifactVersion.context_snapshot_id == write.context_snapshot_id,
                ArtifactVersion.prompt_snapshot_id == write.prompt_snapshot_id,
                ArtifactVersion.content_hash == content_hash,
            )
            .order_by(ArtifactVersion.version_no.desc(), ArtifactVersion.id.desc())
        )
        if existing is not None:
            return existing
        version_no = (
            int(
                self._session.scalar(
                    select(func.coalesce(func.max(ArtifactVersion.version_no), 0)).where(
                        ArtifactVersion.artifact_id == artifact.id
                    )
                )
                or 0
            )
            + 1
        )
        version = ArtifactVersion(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            artifact_id=artifact.id,
            version_no=version_no,
            content_json=content,
            content_hash=content_hash,
            render_summary_json={},
            source_kind="model",
            source_node_run_id=write.node_run_id,
            context_snapshot_id=write.context_snapshot_id,
            prompt_snapshot_id=write.prompt_snapshot_id,
            validation_report_json={"status": "validated", "request_id": write.request_id},
            created_by=self._actor.principal_id,
        )
        self._session.add(version)
        self._session.flush()
        self._submit_version(artifact, version, write)
        return version

    def _submit_version(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        write: GeneratedArtifactWrite,
    ) -> None:
        self._session.add(
            Approval(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                artifact_version_id=version.id,
                node_run_id=write.node_run_id,
                action="submit",
                actor_type=self._actor.actor_type,
                actor_user_id=self._actor.user_id,
                comment=None,
                quality_evidence_json={"status": "validated"},
                policy_snapshot_json={},
                created_by=self._actor.principal_id,
            )
        )
        artifact.current_submitted_version_id = version.id
        artifact.status = "in_review"
        artifact.stale_reason_json = None
        artifact.updated_at = utc_now()
        artifact.updated_by = self._actor.principal_id
        artifact.lock_version += 1
        self._session.flush()

    def _write_relations(self, write: GeneratedArtifactWrite, target_version_id: UUID) -> None:
        service = ArtifactRelationService(self._session, self._actor)
        for relation in write.relations:
            service.add(
                from_version_id=relation.from_artifact_version_id,
                to_version_id=target_version_id,
                relation_type=relation.relation_type.value,
                binding_key=relation.binding_key,
                impact_scope=relation.impact_scope,
            )

    def result_for_version(self, version_id: UUID) -> ArtifactWriteResult:
        row = self._session.execute(
            select(ArtifactVersion, Artifact)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                ArtifactVersion.id == version_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                Artifact.organization_id == self._actor.organization_id,
                Artifact.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            raise ArtifactExecutionPortError(
                "NODE_EXECUTION_ARTIFACT_NOT_FOUND",
                "the committed artifact version is not visible",
            )
        version, artifact = row
        if (
            version.source_node_run_id is None
            or version.context_snapshot_id is None
            or version.prompt_snapshot_id is None
        ):
            raise ArtifactExecutionPortError(
                "NODE_EXECUTION_ARTIFACT_PROVENANCE_MISSING",
                "the committed artifact version lacks execution provenance",
            )
        return ArtifactWriteResult(
            artifact_id=artifact.id,
            artifact_version_id=version.id,
            content_hash=version.content_hash,
            project_id=artifact.project_id,
            node_run_id=version.source_node_run_id,
            context_snapshot_id=version.context_snapshot_id,
            prompt_snapshot_id=version.prompt_snapshot_id,
            artifact_key=artifact.artifact_key,
            artifact_type=artifact.artifact_type,
            branch_key=artifact.branch_key,
            lesson_unit_id=artifact.lesson_unit_id,
            content_definition_version_id=artifact.content_definition_version_id,
        )

    def request_id_for_version(self, version_id: UUID) -> str:
        version = self._session.scalar(
            select(ArtifactVersion).where(
                ArtifactVersion.id == version_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
            )
        )
        if version is None:
            raise ArtifactExecutionPortError(
                "NODE_EXECUTION_ARTIFACT_NOT_FOUND",
                "the committed artifact version is not visible",
            )
        request_id = version.validation_report_json.get("request_id")
        if type(request_id) is not str or not request_id:
            raise ArtifactExecutionPortError(
                "NODE_EXECUTION_ARTIFACT_PROVENANCE_MISSING",
                "the committed artifact version lacks its model request ID",
            )
        return request_id
