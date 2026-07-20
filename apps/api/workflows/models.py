"""Workflow definitions, runs, node state, and immutable input snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, MutableAuditMixin, utc_now

NODE_STATUSES = (
    "disabled",
    "not_ready",
    "ready",
    "draft",
    "queued",
    "running",
    "review_required",
    "approved",
    "partially_completed",
    "failed",
    "paused",
    "cancel_requested",
    "cancelled",
    "stale",
    "skipped",
)


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'disabled')", name="status_allowed"),
        Index("uq_workflow_definitions_workflow_key", "workflow_key", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    workflow_key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class WorkflowDefinitionVersion(Base):
    __tablename__ = "workflow_definition_versions"
    __table_args__ = (
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint(
            "status IN ('draft', 'validated', 'published')",
            name="status_allowed",
        ),
        CheckConstraint(
            "status <> 'published' OR published_at IS NOT NULL",
            name="publication_complete",
        ),
        CheckConstraint("checksum ~ '^[0-9a-f]{64}$'", name="checksum_format"),
        Index(
            "uq_workflow_definition_versions_definition_version",
            "workflow_definition_id",
            "version_no",
            unique=True,
        ),
        Index("uq_workflow_definition_versions_checksum", "checksum", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    workflow_definition_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workflow_definitions.id",
            name="fk_workflow_def_versions_definition",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    graph_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_contract_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowRun(MutableAuditMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        CheckConstraint("run_no > 0", name="run_positive"),
        CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'failed', 'cancelled')",
            name="status_allowed",
        ),
        CheckConstraint("current_event_seq >= 0", name="event_seq_nonnegative"),
        Index("uq_workflow_runs_project_run", "project_id", "run_no", unique=True),
        Index(
            "uq_workflow_runs_project_active",
            "project_id",
            unique=True,
            postgresql_where="status IN ('active', 'paused') AND deleted_at IS NULL",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_definition_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workflow_definition_versions.id",
            name="fk_workflow_runs_definition_version",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    content_release_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("content_releases.id", ondelete="RESTRICT"), nullable=False
    )
    automation_policy_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    run_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BranchRun(MutableAuditMixin, Base):
    __tablename__ = "branch_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('disabled', 'active', 'paused', 'completed', 'failed', 'cancelled')",
            name="status_allowed",
        ),
        Index(
            "uq_branch_runs_workflow_lesson_branch",
            "workflow_run_id",
            "lesson_unit_id",
            "branch_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    workflow_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=False
    )
    lesson_unit_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("lesson_units.id", ondelete="RESTRICT"), nullable=False
    )
    branch_key: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NodeRun(MutableAuditMixin, Base):
    __tablename__ = "node_runs"
    __table_args__ = (
        CheckConstraint("run_no > 0", name="run_positive"),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{status}'" for status in NODE_STATUSES) + ")",
            name="status_allowed",
        ),
        CheckConstraint(
            "trigger_type IN ('manual', 'policy', 'retry', 'system')",
            name="trigger_type_allowed",
        ),
        Index(
            "uq_node_runs_branch_node_run",
            "branch_run_id",
            "node_key",
            "run_no",
            unique=True,
        ),
        Index(
            "uq_node_runs_branch_active",
            "branch_run_id",
            "node_key",
            unique=True,
            postgresql_where=(
                "branch_run_id IS NOT NULL AND "
                "status IN ('queued', 'running', 'cancel_requested') AND deleted_at IS NULL"
            ),
        ),
        Index(
            "uq_node_runs_project_active",
            "workflow_run_id",
            "node_key",
            unique=True,
            postgresql_where=(
                "branch_run_id IS NULL AND "
                "status IN ('queued', 'running', 'cancel_requested') AND deleted_at IS NULL"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=False
    )
    branch_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("branch_runs.id", ondelete="RESTRICT")
    )
    node_key: Mapped[str] = mapped_column(String(160), nullable=False)
    run_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    automation_policy_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    active_artifact_version_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "artifact_versions.id",
            name="fk_node_runs_active_artifact_version",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    stale_reason_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(160))
    execution_owner_token: Mapped[str | None] = mapped_column(String(64))
    execution_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NodeInputSnapshot(Base):
    __tablename__ = "node_input_snapshots"
    __table_args__ = (
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_format"),
        Index(
            "uq_node_input_snapshots_node_input",
            "node_run_id",
            "input_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    node_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("node_runs.id", ondelete="RESTRICT"), nullable=False
    )
    input_key: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
