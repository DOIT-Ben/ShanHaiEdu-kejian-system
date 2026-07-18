"""Creation lifecycle persistence models."""

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
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, MutableAuditMixin


class CreationPackage(Base):
    __tablename__ = "creation_packages"
    __table_args__ = (
        CheckConstraint(
            "package_type IN ('image', 'video', 'presentation')",
            name="package_type_allowed",
        ),
        CheckConstraint(
            "status IN ('building', 'ready', 'invalid', 'expired')",
            name="status_allowed",
        ),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_format"),
        Index("uq_creation_packages_package_key", "package_key", unique=True),
        Index(
            "ix_creation_packages_organization_project_node",
            "organization_id",
            "source_project_id",
            "source_node_run_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    package_key: Mapped[str] = mapped_column(String(180), nullable=False)
    source_project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    source_workflow_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=False
    )
    source_node_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("node_runs.id", ondelete="RESTRICT"), nullable=False
    )
    context_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("context_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    source_prompt_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("prompt_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    package_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    target_rules_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_stale_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )


class CreationPackageItem(Base):
    __tablename__ = "creation_package_items"
    __table_args__ = (
        CheckConstraint("position > 0", name="position_positive"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_format"),
        Index(
            "uq_creation_package_items_package_key",
            "creation_package_id",
            "item_key",
            unique=True,
        ),
        Index(
            "uq_creation_package_items_package_position",
            "creation_package_id",
            "position",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    creation_package_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("creation_packages.id", ondelete="RESTRICT"), nullable=False
    )
    item_key: Mapped[str] = mapped_column(String(160), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    business_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reference_asset_version_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    output_spec_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    target_slot_key: Mapped[str] = mapped_column(String(160), nullable=False)
    consistency_key: Mapped[str | None] = mapped_column(String(160))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class CreationBatch(MutableAuditMixin, Base):
    __tablename__ = "creation_batches"
    __table_args__ = (
        CheckConstraint("source_kind IN ('project', 'standalone')", name="source_kind_allowed"),
        CheckConstraint(
            "studio_type IN ('image', 'video', 'presentation')",
            name="studio_type_allowed",
        ),
        CheckConstraint(
            "status IN ('draft', 'ready', 'running', 'partially_completed', "
            "'completed', 'archived')",
            name="status_allowed",
        ),
        CheckConstraint(
            "(source_kind = 'project' AND creation_package_id IS NOT NULL "
            "AND source_project_id IS NOT NULL AND source_workflow_run_id IS NOT NULL "
            "AND source_node_run_id IS NOT NULL) OR "
            "(source_kind = 'standalone' AND creation_package_id IS NULL "
            "AND source_project_id IS NULL AND source_workflow_run_id IS NULL "
            "AND source_node_run_id IS NULL)",
            name="source_fields_consistent",
        ),
        CheckConstraint(
            "source_kind <> 'standalone' OR owner_user_id IS NOT NULL",
            name="standalone_owner_required",
        ),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        Index("ix_creation_batches_organization_created", "organization_id", "created_at"),
        Index(
            "ix_creation_batches_organization_owner_created",
            "organization_id",
            "owner_user_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    source_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    creation_package_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("creation_packages.id", ondelete="RESTRICT")
    )
    source_project_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT")
    )
    source_workflow_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT")
    )
    source_node_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("node_runs.id", ondelete="RESTRICT")
    )
    studio_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class CreationItem(MutableAuditMixin, Base):
    __tablename__ = "creation_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'ready', 'generating', 'review_required', "
            "'adopted', 'saved', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "(creation_package_item_id IS NULL AND target_slot_key IS NULL) OR "
            "(creation_package_item_id IS NOT NULL AND target_slot_key IS NOT NULL)",
            name="package_target_consistent",
        ),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        Index("uq_creation_items_batch_key", "creation_batch_id", "item_key", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    creation_batch_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("creation_batches.id", ondelete="RESTRICT"), nullable=False
    )
    creation_package_item_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("creation_package_items.id", ondelete="RESTRICT")
    )
    item_key: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    current_prompt_version_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "creation_prompt_versions.id",
            name="fk_creation_items_current_prompt_version",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    active_adoption_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "adoptions.id",
            name="fk_creation_items_active_adoption",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    target_slot_key: Mapped[str | None] = mapped_column(String(160))


class CreationPromptVersion(Base):
    __tablename__ = "creation_prompt_versions"
    __table_args__ = (
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint(
            "generation_profile IN ('quality', 'balanced', 'speed')",
            name="generation_profile_allowed",
        ),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_format"),
        Index(
            "uq_creation_prompt_versions_item_version",
            "creation_item_id",
            "version_no",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    creation_item_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("creation_items.id", ondelete="RESTRICT"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    business_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    reference_asset_version_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    output_spec_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generation_profile: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )


class GenerationResult(Base):
    __tablename__ = "generation_results"
    __table_args__ = (
        CheckConstraint("candidate_no > 0", name="candidate_positive"),
        CheckConstraint(
            "status IN ('available', 'rejected', 'expired')",
            name="status_allowed",
        ),
        CheckConstraint(
            "status <> 'available' OR file_asset_version_id IS NOT NULL",
            name="available_file_present",
        ),
        Index(
            "uq_generation_results_job_candidate",
            "generation_job_id",
            "candidate_no",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    creation_item_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("creation_items.id", ondelete="RESTRICT"), nullable=False
    )
    generation_job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("generation_jobs.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    file_asset_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("file_asset_versions.id", ondelete="RESTRICT")
    )
    output_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Adoption(Base):
    __tablename__ = "adoptions"
    __table_args__ = (
        CheckConstraint(
            "adoption_mode IN ('teacher', 'automation_policy')",
            name="adoption_mode_allowed",
        ),
        Index("ix_adoptions_organization_item", "organization_id", "creation_item_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    creation_item_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("creation_items.id", ondelete="RESTRICT"), nullable=False
    )
    generation_result_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("generation_results.id", ondelete="RESTRICT"), nullable=False
    )
    adoption_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000))
    adopted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    adopted_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )


class SaveToProjectOperation(Base):
    __tablename__ = "save_to_project_operations"
    __table_args__ = (
        CheckConstraint(
            "replace_mode IN ('reject_if_occupied', 'replace_active', 'append')",
            name="replace_mode_allowed",
        ),
        CheckConstraint("status IN ('pending', 'completed')", name="status_allowed"),
        CheckConstraint(
            "(status = 'pending' AND created_binding_id IS NULL AND completed_at IS NULL) OR "
            "(status = 'completed' AND created_binding_id IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="completion_consistent",
        ),
        Index(
            "uq_save_to_project_operations_organization_key",
            "organization_id",
            "idempotency_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_adoption_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("adoptions.id", ondelete="RESTRICT"), nullable=False
    )
    target_project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    target_slot_key: Mapped[str] = mapped_column(String(160), nullable=False)
    replace_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    authorization_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_binding_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "asset_bindings.id",
            name="fk_save_operations_created_binding",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
