"""Published content packages, releases, and immutable definition versions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base


class ContentPackage(Base):
    __tablename__ = "content_packages"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'disabled')", name="status_allowed"),
        Index("uq_content_packages_package_key", "package_key", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    package_key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    package_type: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_scope: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class ContentPackageVersion(Base):
    __tablename__ = "content_package_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'validated', 'published')",
            name="status_allowed",
        ),
        CheckConstraint(
            "status <> 'published' OR (validated_at IS NOT NULL AND published_at IS NOT NULL)",
            name="publication_complete",
        ),
        CheckConstraint("checksum ~ '^[0-9a-f]{64}$'", name="checksum_format"),
        Index(
            "uq_content_package_versions_package_semver",
            "content_package_id",
            "semantic_version",
            unique=True,
        ),
        Index("uq_content_package_versions_checksum", "checksum", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    content_package_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("content_packages.id", ondelete="RESTRICT"), nullable=False
    )
    semantic_version: Mapped[str] = mapped_column(String(80), nullable=False)
    runtime_constraint: Mapped[str] = mapped_column(String(120), nullable=False)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    archive_asset_version_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "file_asset_versions.id",
            name="fk_content_package_versions_archive_asset_version",
            ondelete="RESTRICT",
        ),
    )
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContentPackageItemVersion(Base):
    __tablename__ = "content_package_item_versions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('input_definition', 'content_definition', 'style_preset', "
            "'prompt_template', 'projection_template', 'generation_template')",
            name="kind_allowed",
        ),
        CheckConstraint("checksum ~ '^[0-9a-f]{64}$'", name="checksum_format"),
        Index(
            "uq_content_package_item_versions_package_item",
            "content_package_version_id",
            "item_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    content_package_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "content_package_versions.id",
            name="fk_content_package_items_package_version",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    item_key: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_id: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)


class ContentRelease(Base):
    __tablename__ = "content_releases"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'disabled')", name="status_allowed"),
        CheckConstraint(
            "status <> 'published' OR (published_at IS NOT NULL AND published_by IS NOT NULL)",
            name="publication_complete",
        ),
        Index("uq_content_releases_release_key", "release_key", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    release_key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT")
    )
    notes: Mapped[str | None] = mapped_column(Text)


class ContentReleaseItem(Base):
    __tablename__ = "content_release_items"
    __table_args__ = (
        CheckConstraint("priority >= 0", name="priority_nonnegative"),
        Index(
            "uq_content_release_items_release_mount",
            "content_release_id",
            "mount_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    content_release_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("content_releases.id", ondelete="RESTRICT"), nullable=False
    )
    content_package_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "content_package_versions.id",
            name="fk_content_release_items_package_version",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    mount_key: Mapped[str] = mapped_column(String(160), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)


class RuntimeDefaultVersion(Base):
    __tablename__ = "runtime_default_versions"
    __table_args__ = (
        CheckConstraint("version_no > 0", name="version_positive"),
        Index(
            "uq_runtime_default_versions_key_version",
            "runtime_key",
            "version_no",
            unique=True,
        ),
        Index(
            "uq_runtime_default_versions_release_workflow",
            "runtime_key",
            "content_release_id",
            "workflow_definition_version_id",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    runtime_key: Mapped[str] = mapped_column(String(160), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content_release_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("content_releases.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_definition_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workflow_definition_versions.id",
            name="fk_runtime_defaults_workflow_version",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )


class ContentDefinitionVersion(Base):
    __tablename__ = "content_definition_versions"
    __table_args__ = (
        CheckConstraint("checksum ~ '^[0-9a-f]{64}$'", name="checksum_format"),
        Index(
            "uq_content_definition_versions_package_key",
            "content_package_version_id",
            "definition_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    definition_key: Mapped[str] = mapped_column(String(160), nullable=False)
    content_package_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "content_package_versions.id",
            name="fk_content_def_versions_package_version",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ui_schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    export_mapping_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    validation_rules_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
