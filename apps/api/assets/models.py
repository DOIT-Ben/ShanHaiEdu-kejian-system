"""Stable file asset identities, immutable versions, and material parse records."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
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

from apps.api.database import Base, MutableAuditMixin


class FileAsset(MutableAuditMixin, Base):
    __tablename__ = "file_assets"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'active', 'rejected')", name="status_allowed"),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        Index(
            "uq_file_assets_organization_asset_key_active",
            "organization_id",
            "asset_key",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    asset_key: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    current_version_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "file_asset_versions.id",
            name="fk_file_assets_current_version_id_file_asset_versions",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    retention_class: Mapped[str] = mapped_column(String(40), nullable=False)


class FileAssetVersion(Base):
    __tablename__ = "file_asset_versions"
    __table_args__ = (
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint("byte_size >= 0", name="byte_size_nonnegative"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        CheckConstraint(
            "scan_status IN ('pending', 'clean', 'rejected')", name="scan_status_allowed"
        ),
        CheckConstraint(
            "(width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)",
            name="dimensions_valid",
        ),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="duration_nonnegative"),
        CheckConstraint("page_count IS NULL OR page_count > 0", name="page_count_positive"),
        Index("uq_file_asset_versions_asset_version", "file_asset_id", "version_no", unique=True),
        Index(
            "uq_file_asset_versions_storage_object", "storage_bucket", "storage_key", unique=True
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    file_asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("file_assets.id", ondelete="RESTRICT"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(63), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    etag: Mapped[str] = mapped_column(String(255), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    page_count: Mapped[int | None] = mapped_column(Integer)
    scan_status: Mapped[str] = mapped_column(String(20), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    derived_from_version_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "file_asset_versions.id",
            name="fk_file_asset_versions_derived_from_version",
            ondelete="RESTRICT",
        ),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )


class MaterialParseVersion(Base):
    __tablename__ = "material_parse_versions"
    __table_args__ = (
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint("page_count IS NULL OR page_count > 0", name="page_count_positive"),
        CheckConstraint(
            "text_checksum IS NULL OR text_checksum ~ '^[0-9a-f]{64}$'",
            name="text_checksum_format",
        ),
        CheckConstraint(
            "status <> 'succeeded' OR (content_json IS NOT NULL AND page_count IS NOT NULL "
            "AND text_checksum IS NOT NULL AND completed_at IS NOT NULL)",
            name="success_complete",
        ),
        CheckConstraint(
            "status <> 'failed' OR (error_code IS NOT NULL AND completed_at IS NOT NULL)",
            name="failure_complete",
        ),
        Index(
            "uq_material_parse_versions_material_version",
            "source_material_id",
            "version_no",
            unique=True,
        ),
        Index(
            "ix_material_parse_versions_organization_material",
            "organization_id",
            "source_material_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    source_material_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_materials.id", ondelete="RESTRICT"), nullable=False
    )
    file_asset_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "file_asset_versions.id",
            name="fk_material_parse_versions_file_version",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(120), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    page_count: Mapped[int | None] = mapped_column(Integer)
    text_checksum: Mapped[str | None] = mapped_column(String(64))
    validation_report_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    error_code: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
