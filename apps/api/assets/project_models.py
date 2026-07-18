"""Project asset slot declarations and append-only binding history."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from apps.api.database import Base, MutableAuditMixin


class ProjectAssetSlot(MutableAuditMixin, Base):
    __tablename__ = "project_asset_slots"
    __table_args__ = (
        CheckConstraint("cardinality IN ('one', 'many')", name="cardinality_allowed"),
        CheckConstraint("status IN ('empty', 'satisfied')", name="status_allowed"),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        Index("uq_project_asset_slots_project_key", "project_id", "slot_key", unique=True),
        Index(
            "ix_project_asset_slots_organization_project_lesson_type",
            "organization_id",
            "project_id",
            "lesson_unit_id",
            "asset_type",
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
    slot_key: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(80), nullable=False)
    cardinality: Mapped[str] = mapped_column(String(10), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="empty")
    target_contract_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )


class AssetBinding(Base):
    __tablename__ = "asset_bindings"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint(
            "(is_active AND unbound_at IS NULL AND unbound_by IS NULL) OR "
            "(NOT is_active AND unbound_at IS NOT NULL AND unbound_by IS NOT NULL)",
            name="active_unbound_fields_consistent",
        ),
        Index(
            "uq_asset_bindings_active_slot_position",
            "project_asset_slot_id",
            "position",
            unique=True,
            postgresql_where=expression.column("is_active"),
        ),
        Index(
            "ix_asset_bindings_organization_slot_active",
            "organization_id",
            "project_asset_slot_id",
            "is_active",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_asset_slot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project_asset_slots.id", ondelete="RESTRICT"), nullable=False
    )
    file_asset_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("file_asset_versions.id", ondelete="RESTRICT"), nullable=False
    )
    source_generation_result_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "generation_results.id",
            name="fk_asset_bindings_generation_result",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    source_artifact_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("artifact_versions.id", ondelete="RESTRICT")
    )
    save_operation_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "save_to_project_operations.id",
            name="fk_asset_bindings_save_operation",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bound_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
    unbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unbound_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT")
    )
