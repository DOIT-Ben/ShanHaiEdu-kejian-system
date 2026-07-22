"""Artifact-owned persistence for trusted deterministic node executors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.artifacts.approval_service import ArtifactApprovalService
from apps.api.artifacts.context_source_registry import resolve_artifact_source
from apps.api.artifacts.deterministic_projection import (
    compile_deterministic_identity,
    persist_deterministic_relations,
)
from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.execution_port import SqlAlchemyArtifactPort
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.artifacts.replacement_service import ArtifactReplacementService
from apps.api.artifacts.validation import ArtifactValidation
from apps.api.content_runtime.authoring_policy import AuthoringPolicyUnavailable
from apps.api.content_runtime.authoring_policy_loader import AuthoringPolicyLoader
from apps.api.content_runtime.deterministic_port import DeterministicNodeDefinition
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.database import utc_now
from apps.api.identity.context import ActorContext, ProjectAction, system_actor
from apps.api.ids import new_uuid7
from apps.api.runtime_boundary.contract_values import plain_json_value
from apps.api.runtime_boundary.ports import ArtifactContextVersion, WorkflowExecutionContext


class DeterministicArtifactPortError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DeterministicArtifactFact:
    artifact_id: UUID
    artifact_version_id: UUID
    content_hash: str
    file_asset_version_id: UUID | None


class SqlAlchemyDeterministicArtifactPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._context = SqlAlchemyArtifactPort(session, actor)

    def select_inputs(
        self,
        execution: WorkflowExecutionContext,
        refs: tuple[str, ...],
    ) -> dict[str, ArtifactContextVersion]:
        selected: dict[str, ArtifactContextVersion] = {}
        for ref in refs:
            if resolve_artifact_source(ref) is None:
                continue
            values = self._context.list_context_versions(execution, ref)
            if len(values) != 1:
                raise _error(
                    "PPT_RUNTIME_ARTIFACT_INPUT_INVALID",
                    f"the deterministic input must resolve exactly once: {ref}",
                )
            selected[ref] = values[0]
        return selected

    def load_inputs(
        self,
        execution: WorkflowExecutionContext,
        refs: Mapping[str, UUID],
    ) -> dict[str, ArtifactContextVersion]:
        return self._context.load_frozen_versions(execution, dict(refs))

    def verify_inputs(
        self,
        execution: WorkflowExecutionContext,
        inputs: Mapping[str, ArtifactContextVersion],
    ) -> None:
        self._context.verify_frozen_versions(execution, dict(inputs))

    def persist(
        self,
        definition: DeterministicNodeDefinition,
        execution: WorkflowExecutionContext,
        inputs: Mapping[str, ArtifactContextVersion],
        content: Mapping[str, Any],
        *,
        request_id: str,
    ) -> DeterministicArtifactFact:
        identity = compile_deterministic_identity(definition, execution)
        replacement = ArtifactReplacementService(self._session, self._actor)
        replacement.lock_project_mutation(execution.project_id, action=ProjectAction.GENERATE)
        typed_content = self._validated_content(definition, content)
        content_hash = canonical_content_hash(typed_content)
        artifact = self._get_or_create_artifact(definition, execution, identity)
        version = self._get_or_create_version(
            artifact,
            execution,
            typed_content,
            content_hash,
            request_id=request_id,
            replacement=replacement,
        )
        persist_deterministic_relations(
            self._session,
            self._actor,
            definition,
            execution,
            inputs,
            version.id,
        )
        return _fact(artifact, version)

    def result_for_version(self, version_id: UUID) -> DeterministicArtifactFact:
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
            raise _error("PPT_RUNTIME_RESULT_MISSING", "the committed PPT artifact is missing")
        version, artifact = row
        if (
            version.source_kind != "system"
            or version.source_node_run_id is None
            or version.context_snapshot_id is not None
            or version.prompt_snapshot_id is not None
        ):
            raise _error(
                "PPT_RUNTIME_RESULT_INVALID",
                "the committed PPT artifact has invalid deterministic provenance",
            )
        return _fact(artifact, version)

    def approve_system_output(self, version_id: UUID, *, request_id: str) -> None:
        ArtifactApprovalService(
            self._session,
            system_actor(self._actor.organization_id),
        ).review(
            version_id,
            action="approve",
            comment="Approved deterministic platform output.",
            request_id=request_id,
        )

    def _validated_content(
        self,
        definition: DeterministicNodeDefinition,
        content: Mapping[str, Any],
    ) -> dict[str, Any]:
        value = plain_json_value(content)
        if not isinstance(value, dict):
            raise _error("PPT_RUNTIME_OUTPUT_INVALID", "the deterministic output is not an object")
        typed = cast(dict[str, Any], value)
        row = self._session.get(ContentDefinitionVersion, definition.content_definition_version_id)
        if row is None or row.definition_key != definition.content_definition_key:
            raise _error(
                "PPT_RUNTIME_OUTPUT_DEFINITION_INVALID",
                "the deterministic output definition is unavailable",
            )
        try:
            AuthoringPolicyLoader(self._session).require_by_id(row.id)
        except AuthoringPolicyUnavailable as exc:
            raise _error(
                "AUTHORING_POLICY_UNAVAILABLE",
                "the deterministic output definition has no published authoring policy",
            ) from exc
        report = ArtifactValidation.validation_report(row, typed)
        if not report["valid"]:
            raise _error(
                "PPT_RUNTIME_OUTPUT_INVALID",
                "the deterministic output does not match its published schema",
            )
        return typed

    def _get_or_create_artifact(
        self,
        definition: DeterministicNodeDefinition,
        execution: WorkflowExecutionContext,
        identity: tuple[str, str, str],
    ) -> Artifact:
        artifact_key, artifact_type, branch_key = identity
        artifact = self._session.scalar(
            select(Artifact)
            .where(
                Artifact.organization_id == self._actor.organization_id,
                Artifact.project_id == execution.project_id,
                Artifact.artifact_key == artifact_key,
                Artifact.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if artifact is not None:
            if (
                artifact.lesson_unit_id != execution.lesson_unit_id
                or artifact.artifact_type != artifact_type
                or artifact.branch_key != branch_key
                or artifact.content_definition_version_id
                != definition.content_definition_version_id
            ):
                raise _error(
                    "PPT_RUNTIME_ARTIFACT_IDENTITY_CONFLICT",
                    "the stable PPT artifact identity conflicts with an existing artifact",
                )
            return artifact
        artifact = Artifact(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=execution.project_id,
            lesson_unit_id=execution.lesson_unit_id,
            branch_key=branch_key,
            artifact_key=artifact_key,
            artifact_type=artifact_type,
            content_definition_version_id=definition.content_definition_version_id,
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
        execution: WorkflowExecutionContext,
        content: dict[str, Any],
        content_hash: str,
        *,
        request_id: str,
        replacement: ArtifactReplacementService,
    ) -> ArtifactVersion:
        rows = list(
            self._session.scalars(
                select(ArtifactVersion).where(
                    ArtifactVersion.organization_id == self._actor.organization_id,
                    ArtifactVersion.artifact_id == artifact.id,
                    ArtifactVersion.source_node_run_id == execution.node_run_id,
                )
            )
        )
        if rows:
            if len(rows) == 1 and rows[0].content_hash == content_hash:
                return rows[0]
            raise _error(
                "PPT_RUNTIME_RESULT_CONFLICT",
                "the deterministic node already owns another artifact result",
            )
        version = ArtifactVersion(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            artifact_id=artifact.id,
            version_no=self._next_version_no(artifact.id),
            content_json=content,
            content_hash=content_hash,
            render_summary_json={},
            source_kind="system",
            source_node_run_id=execution.node_run_id,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"status": "validated", "request_id": request_id},
            created_by=self._actor.principal_id,
        )
        self._session.add(version)
        self._session.flush()
        replacement.prepare_generated(
            artifact,
            artifact.current_submitted_version_id,
            version,
            node_run_id=execution.node_run_id,
            carry_incoming_dependencies=False,
        )
        self._submit(artifact, version)
        return version

    def _next_version_no(self, artifact_id: UUID) -> int:
        latest = self._session.scalar(
            select(func.coalesce(func.max(ArtifactVersion.version_no), 0)).where(
                ArtifactVersion.artifact_id == artifact_id
            )
        )
        return int(latest or 0) + 1

    def _submit(self, artifact: Artifact, version: ArtifactVersion) -> None:
        self._session.add(
            Approval(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                artifact_version_id=version.id,
                node_run_id=version.source_node_run_id,
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


def _fact(artifact: Artifact, version: ArtifactVersion) -> DeterministicArtifactFact:
    raw_file_id = version.content_json.get("file_asset_version_id")
    try:
        file_id = UUID(raw_file_id) if isinstance(raw_file_id, str) else None
    except ValueError as exc:
        raise _error(
            "PPT_RUNTIME_RESULT_INVALID",
            "the linked PPTX file identity is invalid",
        ) from exc
    return DeterministicArtifactFact(
        artifact_id=artifact.id,
        artifact_version_id=version.id,
        content_hash=version.content_hash,
        file_asset_version_id=file_id,
    )


def _error(code: str, message: str) -> DeterministicArtifactPortError:
    return DeterministicArtifactPortError(code, message)
