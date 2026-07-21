"""Artifact draft and immutable version application service."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.approval_service import ArtifactApprovalService
from apps.api.artifacts.authoring_guard import ArtifactAuthoringGuard
from apps.api.artifacts.domain import ApprovalAction, canonical_content_hash
from apps.api.artifacts.models import (
    Approval,
    Artifact,
    ArtifactDraft,
    ArtifactRelation,
    ArtifactVersion,
)
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.validation import ArtifactValidation
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.ids import new_uuid7
from apps.api.reliability.events import EventResource, EventWriter


class ArtifactService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = ArtifactRepository(session, actor)
        self._validation = ArtifactValidation(session, actor)
        self._authoring = ArtifactAuthoringGuard(session, actor)

    def create(
        self,
        project_id: UUID,
        *,
        artifact_key: str,
        artifact_type: str,
        branch_key: str,
        content_definition_version_id: UUID,
        draft_branch: str,
        initial_content: dict[str, Any],
        request_id: str | None,
        lesson_unit_id: UUID | None = None,
    ) -> Artifact:
        project = self._validation.require_project(project_id, ProjectAction.EDIT, for_update=True)
        self._validate_identity_field("artifact_key", artifact_key, 160)
        self._validate_identity_field("artifact_type", artifact_type, 80)
        self._validate_identity_field("branch_key", branch_key, 80)
        self._validate_identity_field("draft_branch", draft_branch, 80)
        if self._repository.get_by_key(project_id, artifact_key) is not None:
            raise ApiError(
                status_code=409,
                code="ARTIFACT_KEY_CONFLICT",
                message="The artifact key is already active in this project.",
            )
        self._validation.require_lesson(project_id, lesson_unit_id)
        definition = self._validation.require_definition(
            content_definition_version_id, project.content_release_id
        )
        self._authoring.validate(definition.id, initial_content, baseline=None)
        artifact = self._new_artifact(
            project.id,
            lesson_unit_id,
            artifact_key,
            artifact_type,
            branch_key,
            definition.id,
        )
        self._session.add(artifact)
        self._session.flush()
        draft = self._new_draft(artifact, draft_branch, initial_content, definition)
        self._session.add(draft)
        self._session.flush()
        artifact.current_draft_id = draft.id
        self._session.flush()
        self._append_event(
            project_id=project.id,
            event_type="artifact.created",
            artifact_id=artifact.id,
            payload={"artifact_key": artifact.artifact_key, "draft_id": str(draft.id)},
            request_id=request_id,
        )
        return artifact

    def save_draft(
        self,
        artifact_id: UUID,
        draft_branch: str,
        *,
        expected_lock_version: int,
        content: dict[str, Any],
        request_id: str | None,
    ) -> ArtifactDraft:
        artifact = self._require_artifact(artifact_id, ProjectAction.EDIT, for_update=True)
        draft = self._require_draft(artifact.id, draft_branch, expected_lock_version)
        definition = self._validation.require_artifact_definition(artifact)
        baseline = self._authoring.baseline(artifact, draft)
        self._authoring.validate(definition.id, content, baseline=baseline)
        draft.content_json = content
        draft.validation_report_json = self._validation.validation_report(definition, content)
        draft.autosaved_at = utc_now()
        self._touch(draft)
        artifact.current_draft_id = draft.id
        self._touch(artifact)
        self._session.flush()
        self._append_event(
            project_id=artifact.project_id,
            event_type="artifact.draft.saved",
            artifact_id=artifact.id,
            payload={"draft_id": str(draft.id), "lock_version": draft.lock_version},
            request_id=request_id,
        )
        return draft

    def submit(
        self,
        artifact_id: UUID,
        draft_branch: str,
        *,
        expected_lock_version: int,
        source_kind: str,
        request_id: str | None,
        source_node_run_id: UUID | None = None,
        context_snapshot_id: UUID | None = None,
        prompt_snapshot_id: UUID | None = None,
        render_summary: dict[str, Any] | None = None,
    ) -> ArtifactVersion:
        self._validation.validate_provenance(source_kind, source_node_run_id)
        artifact = self._require_artifact(artifact_id, ProjectAction.EDIT, for_update=True)
        draft = self._require_draft(artifact.id, draft_branch, expected_lock_version)
        content_hash, report = self._validated_submission(artifact, draft)
        existing = self._current_submitted(artifact)
        if existing is not None and existing.content_hash == content_hash:
            return existing
        self._validation.require_source_node(source_node_run_id)
        version = self._new_version(
            artifact,
            draft,
            content_hash,
            report,
            source_kind,
            source_node_run_id,
            context_snapshot_id,
            prompt_snapshot_id,
            render_summary,
        )
        self._session.add(version)
        self._session.flush()
        self._complete_submission(artifact, draft, version, request_id)
        return version

    def review(
        self,
        version_id: UUID,
        *,
        action: str,
        comment: str | None,
        request_id: str | None,
        quality_evidence: dict[str, Any] | None = None,
        policy_snapshot: dict[str, Any] | None = None,
    ) -> Approval:
        return ArtifactApprovalService(self._session, self._actor).review(
            version_id,
            action=action,
            comment=comment,
            request_id=request_id,
            quality_evidence=quality_evidence,
            policy_snapshot=policy_snapshot,
        )

    def add_relation(
        self,
        *,
        from_version_id: UUID,
        to_version_id: UUID,
        relation_type: str,
        binding_key: str,
        impact_scope: dict[str, Any],
    ) -> ArtifactRelation:
        return ArtifactRelationService(self._session, self._actor).add(
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            relation_type=relation_type,
            binding_key=binding_key,
            impact_scope=impact_scope,
        )

    def _new_artifact(
        self,
        project_id: UUID,
        lesson_unit_id: UUID | None,
        artifact_key: str,
        artifact_type: str,
        branch_key: str,
        definition_id: UUID,
    ) -> Artifact:
        return Artifact(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            project_id=project_id,
            lesson_unit_id=lesson_unit_id,
            branch_key=branch_key,
            artifact_key=artifact_key,
            artifact_type=artifact_type,
            content_definition_version_id=definition_id,
            status="draft",
            stale_reason_json=None,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )

    def _new_draft(
        self,
        artifact: Artifact,
        draft_branch: str,
        content: dict[str, Any],
        definition: ContentDefinitionVersion,
    ) -> ArtifactDraft:
        return ArtifactDraft(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            artifact_id=artifact.id,
            draft_branch=draft_branch,
            content_json=content,
            validation_report_json=self._validation.validation_report(definition, content),
            based_on_version_id=None,
            autosaved_at=utc_now(),
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )

    def _validated_submission(
        self,
        artifact: Artifact,
        draft: ArtifactDraft,
    ) -> tuple[str, dict[str, Any]]:
        definition = self._validation.require_artifact_definition(artifact)
        baseline = self._authoring.baseline(artifact, draft)
        self._authoring.validate(definition.id, draft.content_json, baseline=baseline)
        report = self._validation.validation_report(definition, draft.content_json)
        if not report["valid"]:
            raise ApiError(
                status_code=422,
                code="ARTIFACT_CONTENT_INVALID",
                message="The artifact content does not match its published schema.",
                details={"validation": report},
            )
        return canonical_content_hash(draft.content_json), report

    def _new_version(
        self,
        artifact: Artifact,
        draft: ArtifactDraft,
        content_hash: str,
        report: dict[str, Any],
        source_kind: str,
        source_node_run_id: UUID | None,
        context_snapshot_id: UUID | None,
        prompt_snapshot_id: UUID | None,
        render_summary: dict[str, Any] | None,
    ) -> ArtifactVersion:
        return ArtifactVersion(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            artifact_id=artifact.id,
            version_no=self._repository.next_version_no(artifact.id),
            content_json=draft.content_json,
            content_hash=content_hash,
            render_summary_json=render_summary or {},
            source_kind=source_kind,
            source_node_run_id=source_node_run_id,
            context_snapshot_id=context_snapshot_id,
            prompt_snapshot_id=prompt_snapshot_id,
            validation_report_json=report,
            created_by=self._actor.principal_id,
        )

    def _complete_submission(
        self,
        artifact: Artifact,
        draft: ArtifactDraft,
        version: ArtifactVersion,
        request_id: str | None,
    ) -> None:
        self._session.add(self._submission_approval(version))
        artifact.current_submitted_version_id = version.id
        artifact.status = "in_review"
        artifact.stale_reason_json = None
        draft.based_on_version_id = version.id
        self._touch(artifact)
        self._session.flush()
        self._append_event(
            project_id=artifact.project_id,
            event_type="artifact.version.submitted",
            artifact_id=artifact.id,
            payload={"artifact_version_id": str(version.id), "version_no": version.version_no},
            request_id=request_id,
        )

    def _submission_approval(self, version: ArtifactVersion) -> Approval:
        return Approval(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            artifact_version_id=version.id,
            node_run_id=version.source_node_run_id,
            action=ApprovalAction.SUBMIT.value,
            actor_type=self._actor.actor_type,
            actor_user_id=self._actor.user_id,
            comment=None,
            quality_evidence_json={},
            policy_snapshot_json={},
            created_by=self._actor.principal_id,
        )

    def _require_artifact(
        self,
        artifact_id: UUID,
        action: ProjectAction,
        *,
        for_update: bool,
    ) -> Artifact:
        artifact = self._repository.get(artifact_id, for_update=for_update)
        if artifact is None:
            raise self._validation.not_found()
        self._validation.require_project(artifact.project_id, action)
        return artifact

    def _require_draft(
        self,
        artifact_id: UUID,
        draft_branch: str,
        expected_lock_version: int,
    ) -> ArtifactDraft:
        draft = self._repository.get_draft(artifact_id, draft_branch, for_update=True)
        if draft is None:
            raise self._validation.not_found()
        if draft.lock_version != expected_lock_version:
            raise ApiError(
                status_code=409,
                code="EDIT_CONFLICT",
                message="The artifact draft changed after the supplied version.",
                details={"current_lock_version": draft.lock_version},
            )
        return draft

    def _current_submitted(self, artifact: Artifact) -> ArtifactVersion | None:
        if artifact.current_submitted_version_id is None:
            return None
        return self._session.get(ArtifactVersion, artifact.current_submitted_version_id)

    def _append_event(
        self,
        *,
        project_id: UUID,
        event_type: str,
        artifact_id: UUID,
        payload: dict[str, object],
        request_id: str | None,
    ) -> None:
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=project_id,
            event_type=event_type,
            resource=EventResource(type="artifact", id=artifact_id),
            payload=payload,
            request_id=request_id,
        )

    def _touch(self, record: Artifact | ArtifactDraft) -> None:
        record.updated_at = utc_now()
        record.updated_by = self._actor.principal_id
        record.lock_version += 1

    @staticmethod
    def _validate_identity_field(name: str, value: str, maximum: int) -> None:
        if not value.strip() or len(value) > maximum:
            raise ArtifactValidation.invalid(f"The {name} value is invalid.")
