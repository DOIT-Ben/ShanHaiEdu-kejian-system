"""Upload session, source material, and file asset persistence models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, MutableAuditMixin


class SourceMaterial(MutableAuditMixin, Base):
    __tablename__ = "source_materials"
    __table_args__ = (
        CheckConstraint(
            "upload_status IN ('pending_upload', 'confirmed', 'rejected')",
            name="upload_status_allowed",
        ),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        Index("ix_source_materials_organization_project", "organization_id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    material_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="textbook")
    file_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("file_assets.id", ondelete="RESTRICT")
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_status: Mapped[str] = mapped_column(String(30), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT")
    )


class UploadSession(MutableAuditMixin, Base):
    __tablename__ = "upload_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'confirmed', 'expired', 'rejected')",
            name="status_allowed",
        ),
        CheckConstraint("expected_size_bytes > 0", name="size_positive"),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        Index("ix_upload_sessions_organization_project", "organization_id", "project_id"),
        Index("ix_upload_sessions_status_expires", "status", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    material_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_materials.id", ondelete="RESTRICT"), nullable=False
    )
    storage_bucket: Mapped[str] = mapped_column(String(63), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
