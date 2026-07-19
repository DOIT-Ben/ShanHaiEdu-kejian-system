"""Add published content items and versioned runtime defaults.

Revision ID: c2d4e6f8a901
Revises: f1a6c3e9b205
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c2d4e6f8a901"
down_revision: str | Sequence[str] | None = "f1a6c3e9b205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYSTEM_PRINCIPAL_ID = "01900000-0000-7000-8000-000000000002"
BUILTIN_CONTENT_RELEASE_ID = "01970000-0000-7000-8000-000000000003"
BUILTIN_WORKFLOW_DEFINITION_VERSION_ID = "01970000-0000-7000-8000-000000000006"
BUILTIN_RUNTIME_DEFAULT_VERSION_ID = "01970000-0000-7000-8000-000000000007"


def upgrade() -> None:
    _create_content_package_item_versions()
    runtime_defaults = _create_runtime_default_versions()
    op.bulk_insert(
        runtime_defaults,
        [
            {
                "id": BUILTIN_RUNTIME_DEFAULT_VERSION_ID,
                "runtime_key": "primary_math.courseware",
                "version_no": 1,
                "content_release_id": BUILTIN_CONTENT_RELEASE_ID,
                "workflow_definition_version_id": BUILTIN_WORKFLOW_DEFINITION_VERSION_ID,
                "activated_at": datetime(2026, 7, 19, tzinfo=UTC),
                "activated_by": SYSTEM_PRINCIPAL_ID,
            }
        ],
    )
    _create_immutability_triggers()


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_runtime_default_immutable ON runtime_default_versions")
    op.execute("DROP FUNCTION IF EXISTS protect_runtime_default_version()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_content_package_item_immutable ON content_package_item_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_published_package_item_mutation()")
    op.drop_index(
        "uq_runtime_default_versions_release_workflow",
        table_name="runtime_default_versions",
    )
    op.drop_index(
        "uq_runtime_default_versions_key_version",
        table_name="runtime_default_versions",
    )
    op.drop_table("runtime_default_versions")
    op.drop_index(
        "uq_content_package_item_versions_package_item",
        table_name="content_package_item_versions",
    )
    op.drop_table("content_package_item_versions")


def _create_content_package_item_versions() -> None:
    op.create_table(
        "content_package_item_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_package_version_id", sa.Uuid(), nullable=False),
        sa.Column("item_key", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("schema_id", sa.String(length=500), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "kind IN ('input_definition', 'content_definition', 'style_preset', "
            "'prompt_template', 'projection_template', 'generation_template')",
            name=op.f("ck_content_package_item_versions_kind_allowed"),
        ),
        sa.CheckConstraint(
            "checksum ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_content_package_item_versions_checksum_format"),
        ),
        sa.ForeignKeyConstraint(
            ["content_package_version_id"],
            ["content_package_versions.id"],
            name="fk_content_package_items_package_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_package_item_versions")),
    )
    op.create_index(
        "uq_content_package_item_versions_package_item",
        "content_package_item_versions",
        ["content_package_version_id", "item_key"],
        unique=True,
    )


def _create_runtime_default_versions() -> sa.Table:
    table = op.create_table(
        "runtime_default_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("runtime_key", sa.String(length=160), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content_release_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "version_no > 0",
            name=op.f("ck_runtime_default_versions_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["activated_by"],
            ["principals.id"],
            name=op.f("fk_runtime_default_versions_activated_by_principals"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["content_release_id"],
            ["content_releases.id"],
            name=op.f("fk_runtime_default_versions_content_release_id_content_releases"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_definition_version_id"],
            ["workflow_definition_versions.id"],
            name="fk_runtime_defaults_workflow_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runtime_default_versions")),
    )
    op.create_index(
        "uq_runtime_default_versions_key_version",
        "runtime_default_versions",
        ["runtime_key", "version_no"],
        unique=True,
    )
    op.create_index(
        "uq_runtime_default_versions_release_workflow",
        "runtime_default_versions",
        ["runtime_key", "content_release_id", "workflow_definition_version_id"],
        unique=True,
    )
    return table


def _create_immutability_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_published_package_item_mutation()
        RETURNS trigger AS $$
        DECLARE package_version_id uuid;
        BEGIN
            package_version_id := CASE WHEN TG_OP = 'DELETE'
                THEN OLD.content_package_version_id ELSE NEW.content_package_version_id END;
            IF EXISTS (SELECT 1 FROM content_package_versions
                       WHERE id = package_version_id AND status = 'published') THEN
                RAISE EXCEPTION 'published content package items are immutable'
                    USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_content_package_item_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON content_package_item_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_published_package_item_mutation();

        CREATE FUNCTION protect_runtime_default_version()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'runtime default versions are immutable'
                    USING ERRCODE = '23514';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM content_releases
                           WHERE id = NEW.content_release_id AND status = 'published') THEN
                RAISE EXCEPTION 'runtime default requires a published content release'
                    USING ERRCODE = '23514';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM workflow_definition_versions
                           WHERE id = NEW.workflow_definition_version_id
                             AND status = 'published') THEN
                RAISE EXCEPTION 'runtime default requires a published workflow version'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_runtime_default_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON runtime_default_versions
        FOR EACH ROW EXECUTE FUNCTION protect_runtime_default_version();
        """
    )
