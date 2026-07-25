"""Artifact ORM-to-API response projection."""

from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.artifacts.models import Approval, Artifact, ArtifactDraft, ArtifactVersion
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.schemas import (
    ApprovalRead,
    ArtifactDraftRead,
    ArtifactRead,
    ArtifactVersionRead,
)
from apps.api.identity.context import ActorContext


def serialize_artifact(
    session: Session,
    actor: ActorContext,
    artifact: Artifact,
) -> ArtifactRead:
    repository = ArtifactRepository(session, actor)
    current_draft = (
        session.get(ArtifactDraft, artifact.current_draft_id)
        if artifact.current_draft_id is not None
        else None
    )
    submitted = (
        repository.get_version(artifact.current_submitted_version_id)
        if artifact.current_submitted_version_id is not None
        else None
    )
    approved = (
        repository.get_version(artifact.current_approved_version_id)
        if artifact.current_approved_version_id is not None
        else None
    )
    return ArtifactRead.model_validate(
        {
            "id": artifact.id,
            "project_id": artifact.project_id,
            "lesson_unit_id": artifact.lesson_unit_id,
            "branch_key": artifact.branch_key,
            "artifact_key": artifact.artifact_key,
            "artifact_type": artifact.artifact_type,
            "content_definition_version_id": artifact.content_definition_version_id,
            "status": artifact.status,
            "stale_reason": artifact.stale_reason_json,
            "lock_version": artifact.lock_version,
            "current_draft": (
                serialize_draft(current_draft) if current_draft is not None else None
            ),
            "current_submitted_version": (
                serialize_version(submitted[0]) if submitted is not None else None
            ),
            "current_approved_version": (
                serialize_version(approved[0]) if approved is not None else None
            ),
            "created_at": artifact.created_at,
            "updated_at": artifact.updated_at,
        }
    )


def serialize_draft(draft: ArtifactDraft) -> ArtifactDraftRead:
    return ArtifactDraftRead(
        id=draft.id,
        draft_branch=draft.draft_branch,
        content=draft.content_json,
        validation_report=draft.validation_report_json,
        based_on_version_id=draft.based_on_version_id,
        autosaved_at=draft.autosaved_at,
        lock_version=draft.lock_version,
    )


def serialize_version(version: ArtifactVersion) -> ArtifactVersionRead:
    return ArtifactVersionRead.model_validate(
        {
            "id": version.id,
            "version_no": version.version_no,
            "content": version.content_json,
            "content_hash": version.content_hash,
            "render_summary": version.render_summary_json,
            "source_kind": version.source_kind,
            "source_node_run_id": version.source_node_run_id,
            "context_snapshot_id": version.context_snapshot_id,
            "prompt_snapshot_id": version.prompt_snapshot_id,
            "validation_report": version.validation_report_json,
            "created_at": version.created_at,
            "created_by": version.created_by,
        }
    )


def serialize_approval(approval: Approval) -> ApprovalRead:
    return ApprovalRead.model_validate(
        {
            "id": approval.id,
            "artifact_version_id": approval.artifact_version_id,
            "action": approval.action,
            "actor_type": approval.actor_type,
            "actor_user_id": approval.actor_user_id,
            "comment": approval.comment,
            "quality_evidence": approval.quality_evidence_json,
            "policy_snapshot": approval.policy_snapshot_json,
            "created_at": approval.created_at,
        }
    )
