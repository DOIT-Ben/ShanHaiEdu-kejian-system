"""Lesson unit and branch configuration persistence models."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, MutableAuditMixin


class LessonUnit(MutableAuditMixin, Base):
    __tablename__ = "lesson_units"
    __table_args__ = (
        CheckConstraint("position > 0", name="position_positive"),
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="estimated_minutes_positive",
        ),
        CheckConstraint("status IN ('active', 'archived')", name="status_allowed"),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        UniqueConstraint("project_id", "lesson_key", name="uq_lesson_units_project_lesson_key"),
        UniqueConstraint("project_id", "position", name="uq_lesson_units_project_position"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    lesson_key: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_summary: Mapped[str] = mapped_column(Text, nullable=False)
    objective_summary: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    source_division_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class LessonBranchConfig(MutableAuditMixin, Base):
    __tablename__ = "lesson_branch_configs"
    __table_args__ = (
        CheckConstraint(
            "branch_key IN ('lesson_plan', 'intro_options', 'ppt', 'video')",
            name="branch_key_allowed",
        ),
        CheckConstraint(
            "branch_key <> 'lesson_plan' OR enabled",
            name="lesson_plan_enabled",
        ),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        UniqueConstraint(
            "lesson_unit_id",
            "branch_key",
            name="uq_lesson_branch_configs_lesson_branch",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    lesson_unit_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("lesson_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    branch_key: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
