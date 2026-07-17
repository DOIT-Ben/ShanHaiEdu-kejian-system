"""Extend file assets and add material parse versions.

Revision ID: f4c8d2e6a103
Revises: e8f4a2b7c901
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f4c8d2e6a103"
down_revision: str | Sequence[str] | None = "e8f4a2b7c901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("file_asset_versions", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("file_asset_versions", sa.Column("height", sa.Integer(), nullable=True))
    op.add_column("file_asset_versions", sa.Column("duration_ms", sa.BigInteger(), nullable=True))
    op.add_column("file_asset_versions", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column(
        "file_asset_versions",
        sa.Column("derived_from_version_id", sa.Uuid(), nullable=True),
    )
    op.create_check_constraint(
        "ck_file_asset_versions_sha256_format",
        "file_asset_versions",
        "sha256 ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "ck_file_asset_versions_dimensions_valid",
        "file_asset_versions",
        "(width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)",
    )
    op.create_check_constraint(
        "ck_file_asset_versions_duration_nonnegative",
        "file_asset_versions",
        "duration_ms IS NULL OR duration_ms >= 0",
    )
    op.create_check_constraint(
        "ck_file_asset_versions_page_count_positive",
        "file_asset_versions",
        "page_count IS NULL OR page_count > 0",
    )
    op.create_foreign_key(
        "fk_file_asset_versions_derived_from_version",
        "file_asset_versions",
        "file_asset_versions",
        ["derived_from_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    _create_file_version_immutability_trigger()
    op.create_table(
        "material_parse_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_material_id", sa.Uuid(), nullable=False),
        sa.Column("file_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("parser_name", sa.String(length=120), nullable=False),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("text_checksum", sa.String(length=64), nullable=True),
        sa.Column(
            "validation_report_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_material_parse_versions_status_allowed",
        ),
        sa.CheckConstraint(
            "version_no > 0",
            name="ck_material_parse_versions_version_positive",
        ),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count > 0",
            name="ck_material_parse_versions_page_count_positive",
        ),
        sa.CheckConstraint(
            "text_checksum IS NULL OR text_checksum ~ '^[0-9a-f]{64}$'",
            name="ck_material_parse_versions_text_checksum_format",
        ),
        sa.CheckConstraint(
            "status <> 'succeeded' OR (content_json IS NOT NULL AND page_count IS NOT NULL "
            "AND text_checksum IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_material_parse_versions_success_complete",
        ),
        sa.CheckConstraint(
            "status <> 'failed' OR (error_code IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_material_parse_versions_failure_complete",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_material_parse_versions_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_material_id"],
            ["source_materials.id"],
            name="fk_material_parse_versions_source_material_id_source_materials",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["file_asset_version_id"],
            ["file_asset_versions.id"],
            name="fk_material_parse_versions_file_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["principals.id"],
            name="fk_material_parse_versions_created_by_principals",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["principals.id"],
            name="fk_material_parse_versions_updated_by_principals",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_material_parse_versions"),
    )
    op.create_index(
        "uq_material_parse_versions_material_version",
        "material_parse_versions",
        ["source_material_id", "version_no"],
        unique=True,
    )
    op.create_index(
        "ix_material_parse_versions_organization_material",
        "material_parse_versions",
        ["organization_id", "source_material_id"],
    )
    _create_parse_immutability_trigger()


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_material_parse_terminal_immutable ON material_parse_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_material_parse_terminal_update()")
    op.drop_index(
        "ix_material_parse_versions_organization_material",
        table_name="material_parse_versions",
    )
    op.drop_index(
        "uq_material_parse_versions_material_version",
        table_name="material_parse_versions",
    )
    op.drop_table("material_parse_versions")
    op.execute("DROP TRIGGER IF EXISTS trg_file_asset_version_immutable ON file_asset_versions")
    op.execute("DROP FUNCTION IF EXISTS prevent_file_asset_version_core_update()")
    op.drop_constraint(
        "fk_file_asset_versions_derived_from_version",
        "file_asset_versions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_file_asset_versions_page_count_positive", "file_asset_versions", type_="check"
    )
    op.drop_constraint(
        "ck_file_asset_versions_duration_nonnegative", "file_asset_versions", type_="check"
    )
    op.drop_constraint(
        "ck_file_asset_versions_dimensions_valid", "file_asset_versions", type_="check"
    )
    op.drop_constraint("ck_file_asset_versions_sha256_format", "file_asset_versions", type_="check")
    op.drop_column("file_asset_versions", "derived_from_version_id")
    op.drop_column("file_asset_versions", "page_count")
    op.drop_column("file_asset_versions", "duration_ms")
    op.drop_column("file_asset_versions", "height")
    op.drop_column("file_asset_versions", "width")


def _create_file_version_immutability_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_file_asset_version_core_update()
        RETURNS trigger AS $$
        BEGIN
            IF ROW(OLD.organization_id, OLD.file_asset_id, OLD.version_no,
                   OLD.storage_bucket, OLD.storage_key, OLD.mime_type,
                   OLD.byte_size, OLD.sha256, OLD.etag, OLD.derived_from_version_id,
                   OLD.created_at, OLD.created_by)
               IS DISTINCT FROM
               ROW(NEW.organization_id, NEW.file_asset_id, NEW.version_no,
                   NEW.storage_bucket, NEW.storage_key, NEW.mime_type,
                   NEW.byte_size, NEW.sha256, NEW.etag, NEW.derived_from_version_id,
                   NEW.created_at, NEW.created_by) THEN
                RAISE EXCEPTION 'file asset version core fields are immutable'
                    USING ERRCODE = '23514';
            END IF;
            IF (OLD.width IS NOT NULL AND NEW.width IS DISTINCT FROM OLD.width)
               OR (OLD.height IS NOT NULL AND NEW.height IS DISTINCT FROM OLD.height)
               OR (OLD.duration_ms IS NOT NULL AND NEW.duration_ms IS DISTINCT FROM OLD.duration_ms)
               OR (OLD.page_count IS NOT NULL AND NEW.page_count IS DISTINCT FROM OLD.page_count)
            THEN
                RAISE EXCEPTION 'file asset version enriched metadata is immutable once set'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_file_asset_version_immutable
        BEFORE UPDATE ON file_asset_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_file_asset_version_core_update();
        """
    )


def _create_parse_immutability_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_material_parse_terminal_update()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status IN ('succeeded', 'failed') AND NEW IS DISTINCT FROM OLD THEN
                RAISE EXCEPTION 'terminal material parse versions are immutable'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_material_parse_terminal_immutable
        BEFORE UPDATE ON material_parse_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_material_parse_terminal_update();
        """
    )
