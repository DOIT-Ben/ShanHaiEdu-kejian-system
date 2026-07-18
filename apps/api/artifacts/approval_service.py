"""Artifact approval state machine and transactional event writes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.domain import ApprovalAction
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.creation.staleness_service import CreationPackageStalenessService
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction, ProjectRole
from apps.api.identity.models import ProjectMember
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.projects.models import Project
from apps.api.reliability.events import EventResource, EventWriter


class ArtifactApprovalService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = ArtifactRepository(session, actor)
        self._relations = ArtifactRelationService(session, actor)

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
        resolved_action = self._parse_action(action)
        record = self._repository.get_version(version_id, for_update_artifact=True)
        if record is None:
            raise self._not_found()
        version, artifact = record
        self._require_project(artifact.project_id)
        if resolved_action is ApprovalAction.APPROVE:
            return self._approve(
                artifact,
                version,
                comment,
                request_id,
                quality_evidence,
                policy_snapshot,
            )
        if resolved_action is ApprovalAction.ACCEPT_STALE:
            return self._accept_stale(
                artifact,
                version,
                comment,
                request_id,
                quality_evidence,
                policy_snapshot,
            )
        if resolved_action is ApprovalAction.REQUEST_CHANGES:
            return self._request_changes(
                artifact,
                version,
                comment,
                request_id,
                quality_evidence,
                policy_snapshot,
            )
        return self._revoke(
            artifact,
            version,
            comment,
            request_id,
            quality_evidence,
            policy_snapshot,
        )

    def _approve(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        comment: str | None,
        request_id: str | None,
        quality_evidence: dict[str, Any] | None,
        policy_snapshot: dict[str, Any] | None,
    ) -> Approval:
        existing = self._repository.latest_action(version.id, ApprovalAction.APPROVE.value)
        if artifact.current_approved_version_id == version.id and existing is not None:
            return existing
        if artifact.current_submitted_version_id != version.id:
            raise self._state_conflict("Only the current submitted version can be approved.")
        previous_version_id = artifact.current_approved_version_id
        approval = self._record(
            version, ApprovalAction.APPROVE, comment, quality_evidence, policy_snapshot
        )
        artifact.current_approved_version_id = version.id
        artifact.status = "approved"
        artifact.stale_reason_json = None
        stale_ids, stale_node_ids = self._relations.propagate_stale(previous_version_id, version.id)
        CreationPackageStalenessService(
            self._session, self._actor.organization_id
        ).mark_source_nodes_stale(stale_node_ids)
        self._touch(artifact)
        self._session.flush()
        self._append_event(
            artifact,
            "artifact.version.approved",
            {
                "artifact_version_id": str(version.id),
                "previous_version_id": (
                    str(previous_version_id) if previous_version_id is not None else None
                ),
                "stale_artifact_ids": [str(item) for item in stale_ids],
            },
            request_id,
        )
        self._append_stale_event(artifact, version.id, stale_ids, request_id)
        return approval

    def _accept_stale(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        comment: str | None,
        request_id: str | None,
        quality_evidence: dict[str, Any] | None,
        policy_snapshot: dict[str, Any] | None,
    ) -> Approval:
        if artifact.current_approved_version_id != version.id or artifact.status != "stale":
            raise self._state_conflict("Only the current stale approved version can be accepted.")
        approval = self._record(
            version,
            ApprovalAction.ACCEPT_STALE,
            comment,
            quality_evidence,
            policy_snapshot,
        )
        artifact.status = "approved"
        artifact.stale_reason_json = None
        self._touch(artifact)
        self._session.flush()
        self._append_simple_event(artifact, version, ApprovalAction.ACCEPT_STALE, request_id)
        return approval

    def _request_changes(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        comment: str | None,
        request_id: str | None,
        quality_evidence: dict[str, Any] | None,
        policy_snapshot: dict[str, Any] | None,
    ) -> Approval:
        if artifact.current_submitted_version_id != version.id:
            raise self._state_conflict("Only the current submitted version can be returned.")
        approval = self._record(
            version,
            ApprovalAction.REQUEST_CHANGES,
            comment,
            quality_evidence,
            policy_snapshot,
        )
        artifact.current_submitted_version_id = None
        artifact.status = "draft"
        self._touch(artifact)
        self._session.flush()
        self._append_simple_event(artifact, version, ApprovalAction.REQUEST_CHANGES, request_id)
        return approval

    def _revoke(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        comment: str | None,
        request_id: str | None,
        quality_evidence: dict[str, Any] | None,
        policy_snapshot: dict[str, Any] | None,
    ) -> Approval:
        if not comment or not comment.strip():
            raise self._invalid("Revoking an approval requires a reason.")
        self._require_owner(artifact.project_id)
        if artifact.current_approved_version_id != version.id:
            raise self._state_conflict("Only the current approved version can be revoked.")
        approval = self._record(
            version, ApprovalAction.REVOKE, comment, quality_evidence, policy_snapshot
        )
        artifact.current_approved_version_id = None
        stale_ids, stale_node_ids = self._relations.propagate_stale(version.id, None)
        CreationPackageStalenessService(
            self._session, self._actor.organization_id
        ).mark_source_nodes_stale(stale_node_ids)
        artifact.status = (
            "in_review" if artifact.current_submitted_version_id is not None else "draft"
        )
        artifact.stale_reason_json = None
        self._touch(artifact)
        self._session.flush()
        self._append_event(
            artifact,
            "artifact.version.revoke",
            {
                "artifact_version_id": str(version.id),
                "stale_artifact_ids": [str(item) for item in stale_ids],
            },
            request_id,
        )
        self._append_stale_event(artifact, version.id, stale_ids, request_id)
        return approval

    def _record(
        self,
        version: ArtifactVersion,
        action: ApprovalAction,
        comment: str | None,
        quality_evidence: dict[str, Any] | None,
        policy_snapshot: dict[str, Any] | None,
    ) -> Approval:
        approval = Approval(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            artifact_version_id=version.id,
            node_run_id=version.source_node_run_id,
            action=action.value,
            actor_type=self._actor.actor_type,
            actor_user_id=self._actor.user_id,
            comment=comment,
            quality_evidence_json=quality_evidence or {},
            policy_snapshot_json=policy_snapshot or {},
            created_by=self._actor.principal_id,
        )
        self._session.add(approval)
        return approval

    def _append_simple_event(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        action: ApprovalAction,
        request_id: str | None,
    ) -> None:
        self._append_event(
            artifact,
            f"artifact.version.{action.value}",
            {"artifact_version_id": str(version.id)},
            request_id,
        )

    def _append_event(
        self,
        artifact: Artifact,
        event_type: str,
        payload: dict[str, object],
        request_id: str | None,
    ) -> None:
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=artifact.project_id,
            event_type=event_type,
            resource=EventResource(type="artifact", id=artifact.id),
            payload=payload,
            request_id=request_id,
        )

    def _append_stale_event(
        self,
        artifact: Artifact,
        source_version_id: UUID,
        stale_ids: list[UUID],
        request_id: str | None,
    ) -> None:
        if not stale_ids:
            return
        EventWriter(self._session, self._actor.organization_id).append(
            project_id=artifact.project_id,
            event_type="workflow.downstream_stale.propagated",
            resource=EventResource(type="artifact", id=artifact.id),
            payload={
                "source_version_id": str(source_version_id),
                "affected_resource_ids": [str(item) for item in stale_ids],
                "reason_code": "UPSTREAM_APPROVED_VERSION_CHANGED",
            },
            request_id=request_id,
        )

    def _require_project(self, project_id: UUID) -> Project:
        if not self._actor.is_system:
            return ProjectAccessService(self._session, self._actor).require(
                project_id, ProjectAction.REVIEW
            )
        project = self._session.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == self._actor.organization_id,
                Project.deleted_at.is_(None),
            )
        )
        if project is None:
            raise self._not_found()
        return project

    def _require_owner(self, project_id: UUID) -> None:
        if self._actor.is_system:
            return
        role = self._session.scalar(
            select(ProjectMember.role).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == self._actor.user_id,
            )
        )
        if role != ProjectRole.OWNER.value:
            raise ApiError(
                status_code=403,
                code="PERMISSION_DENIED",
                message="Only a project owner can revoke an approval.",
            )

    @staticmethod
    def _parse_action(action: str) -> ApprovalAction:
        try:
            resolved = ApprovalAction(action)
        except ValueError as exc:
            raise ArtifactApprovalService._invalid("The approval action is invalid.") from exc
        if resolved is ApprovalAction.SUBMIT:
            raise ArtifactApprovalService._invalid(
                "Submit the active draft through the version command."
            )
        return resolved

    def _touch(self, artifact: Artifact) -> None:
        artifact.updated_at = utc_now()
        artifact.updated_by = self._actor.principal_id
        artifact.lock_version += 1

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="ARTIFACT_NOT_FOUND",
            message="The artifact resource was not found.",
        )

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(status_code=422, code="INVALID_ARTIFACT", message=message)

    @staticmethod
    def _state_conflict(message: str) -> ApiError:
        return ApiError(status_code=409, code="ARTIFACT_STATE_CONFLICT", message=message)
