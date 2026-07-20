"""Artifact persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, MutableAuditMixin, utc_now


class Artifact(MutableAuditMixin, Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'stale', 'archived')",
            name="status_allowed",
        ),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        Index(
            "uq_artifacts_project_key_active",
            "project_id",
            "artifact_key",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_artifacts_organization_project_branch",
            "organization_id",
            "project_id",
            "lesson_unit_id",
            "branch_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    lesson_unit_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("lesson_units.id", ondelete="RESTRICT")
    )
    branch_key: Mapped[str] = mapped_column(String(80), nullable=False)
    artifact_key: Mapped[str] = mapped_column(String(160), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_definition_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "content_definition_versions.id",
            name="fk_artifacts_content_definition_version",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    current_draft_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "artifact_drafts.id",
            name="fk_artifacts_current_draft",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    current_submitted_version_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "artifact_versions.id",
            name="fk_artifacts_current_submitted_version",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    current_approved_version_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "artifact_versions.id",
            name="fk_artifacts_current_approved_version",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    stale_reason_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_format"),
        CheckConstraint(
            "source_kind IN ('manual', 'model', 'import', 'system')",
            name="source_kind_allowed",
        ),
        Index(
            "uq_artifact_versions_artifact_version",
            "artifact_id",
            "version_no",
            unique=True,
        ),
        Index(
            "ix_artifact_versions_organization_artifact_created",
            "organization_id",
            "artifact_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    artifact_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    render_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    source_node_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("node_runs.id", ondelete="RESTRICT")
    )
    context_snapshot_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "context_snapshots.id",
            name="fk_artifact_versions_context_snapshot",
            ondelete="RESTRICT",
        ),
    )
    prompt_snapshot_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "prompt_snapshots.id",
            name="fk_artifact_versions_prompt_snapshot",
            ondelete="RESTRICT",
        ),
    )
    validation_report_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )


class ArtifactDraft(MutableAuditMixin, Base):
    __tablename__ = "artifact_drafts"
    __table_args__ = (
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        Index(
            "uq_artifact_drafts_artifact_branch_active",
            "artifact_id",
            "draft_branch",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_artifact_drafts_organization_artifact",
            "organization_id",
            "artifact_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    artifact_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    draft_branch: Mapped[str] = mapped_column(String(80), nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    validation_report_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    based_on_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifact_versions.id", ondelete="RESTRICT")
    )
    autosaved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "action IN ('submit', 'approve', 'request_changes', 'revoke', 'accept_stale')",
            name="action_allowed",
        ),
        CheckConstraint("actor_type IN ('user', 'system')", name="actor_type_allowed"),
        CheckConstraint(
            "(actor_type = 'system' AND actor_user_id IS NULL) OR "
            "(actor_type = 'user' AND actor_user_id IS NOT NULL)",
            name="actor_user_link",
        ),
        Index(
            "ix_approvals_organization_version_created",
            "organization_id",
            "artifact_version_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    artifact_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifact_versions.id", ondelete="RESTRICT"), nullable=False
    )
    node_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("node_runs.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    comment: Mapped[str | None] = mapped_column(Text)
    quality_evidence_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    policy_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )


class ArtifactRelation(Base):
    __tablename__ = "artifact_relations"
    __table_args__ = (
        CheckConstraint(
            "relation_type IN ('derives_from', 'references', 'constrains', 'supersedes')",
            name="relation_type_allowed",
        ),
        CheckConstraint(
            "from_artifact_version_id <> to_artifact_version_id",
            name="no_self_relation",
        ),
        CheckConstraint(
            "shanhai_is_canonical_impact_scope(impact_scope_json)",
            name="impact_scope_allowed",
        ),
        Index(
            "uq_artifact_relations_versions_binding",
            "from_artifact_version_id",
            "to_artifact_version_id",
            "relation_type",
            "binding_key",
            unique=True,
        ),
        Index(
            "ix_artifact_relations_organization_from",
            "organization_id",
            "from_artifact_version_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    from_artifact_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifact_versions.id", ondelete="RESTRICT"), nullable=False
    )
    to_artifact_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifact_versions.id", ondelete="RESTRICT"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    binding_key: Mapped[str] = mapped_column(String(160), nullable=False)
    impact_scope_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
