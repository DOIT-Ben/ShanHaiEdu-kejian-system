"""Add project asset slots and append-only binding history.

Revision ID: b4a7c2d9e805
Revises: a9e1f3c5b704
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b4a7c2d9e805"
down_revision: str | Sequence[str] | None = "a9e1f3c5b704"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_project_asset_slots()
    _create_asset_bindings()
    _create_scope_and_history_triggers()


def downgrade() -> None:
    _drop_scope_and_history_triggers()
    op.drop_index("ix_asset_bindings_organization_slot_active", table_name="asset_bindings")
    op.drop_index("uq_asset_bindings_active_slot_position", table_name="asset_bindings")
    op.drop_table("asset_bindings")
    op.drop_index(
        "ix_project_asset_slots_organization_project_lesson_type",
        table_name="project_asset_slots",
    )
    op.drop_index("uq_project_asset_slots_project_key", table_name="project_asset_slots")
    op.drop_table("project_asset_slots")


def _create_project_asset_slots() -> None:
    op.create_table(
        "project_asset_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_unit_id", sa.Uuid(), nullable=True),
        sa.Column("slot_key", sa.String(length=160), nullable=False),
        sa.Column("asset_type", sa.String(length=80), nullable=False),
        sa.Column("cardinality", sa.String(length=10), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("target_contract_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "cardinality IN ('one', 'many')",
            name="ck_project_asset_slots_cardinality_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('empty', 'satisfied')",
            name="ck_project_asset_slots_status_allowed",
        ),
        sa.CheckConstraint(
            "lock_version >= 1",
            name="ck_project_asset_slots_lock_version_positive",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lesson_unit_id"], ["lesson_units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_project_asset_slots"),
    )
    op.create_index(
        "uq_project_asset_slots_project_key",
        "project_asset_slots",
        ["project_id", "slot_key"],
        unique=True,
    )
    op.create_index(
        "ix_project_asset_slots_organization_project_lesson_type",
        "project_asset_slots",
        ["organization_id", "project_id", "lesson_unit_id", "asset_type"],
    )


def _create_asset_bindings() -> None:
    op.create_table(
        "asset_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_asset_slot_id", sa.Uuid(), nullable=False),
        sa.Column("file_asset_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_generation_result_id", sa.Uuid(), nullable=True),
        sa.Column("source_artifact_version_id", sa.Uuid(), nullable=True),
        sa.Column("save_operation_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bound_by", sa.Uuid(), nullable=False),
        sa.Column("unbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unbound_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("position >= 0", name="ck_asset_bindings_position_nonnegative"),
        sa.CheckConstraint(
            "(is_active AND unbound_at IS NULL AND unbound_by IS NULL) OR "
            "(NOT is_active AND unbound_at IS NOT NULL AND unbound_by IS NOT NULL)",
            name="ck_asset_bindings_active_unbound_fields_consistent",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_asset_slot_id"], ["project_asset_slots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["file_asset_version_id"], ["file_asset_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_version_id"], ["artifact_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["bound_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unbound_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_asset_bindings"),
    )
    op.create_index(
        "uq_asset_bindings_active_slot_position",
        "asset_bindings",
        ["project_asset_slot_id", "position"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_asset_bindings_organization_slot_active",
        "asset_bindings",
        ["organization_id", "project_asset_slot_id", "is_active"],
    )


def _create_scope_and_history_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION validate_project_asset_slot_scope() RETURNS trigger AS $$
        DECLARE
          project_organization uuid;
          lesson_project uuid;
          lesson_organization uuid;
        BEGIN
          SELECT organization_id INTO project_organization
          FROM projects WHERE id = NEW.project_id AND deleted_at IS NULL;
          IF project_organization IS NULL OR project_organization <> NEW.organization_id THEN
            RAISE EXCEPTION 'project asset slot organization does not match project';
          END IF;
          IF NEW.lesson_unit_id IS NOT NULL THEN
            SELECT project_id, organization_id INTO lesson_project, lesson_organization
            FROM lesson_units WHERE id = NEW.lesson_unit_id AND deleted_at IS NULL;
            IF lesson_project IS NULL
               OR lesson_project <> NEW.project_id
               OR lesson_organization <> NEW.organization_id THEN
              RAISE EXCEPTION 'project asset slot lesson does not match project';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_project_asset_slot_scope
        BEFORE INSERT OR UPDATE ON project_asset_slots
        FOR EACH ROW EXECUTE FUNCTION validate_project_asset_slot_scope();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_asset_binding_scope() RETURNS trigger AS $$
        DECLARE
          slot_organization uuid;
          slot_project uuid;
          slot_lesson uuid;
          slot_cardinality text;
          slot_asset_type text;
          file_organization uuid;
          file_asset_type text;
          source_organization uuid;
          source_project uuid;
          source_lesson uuid;
        BEGIN
          SELECT organization_id, project_id, lesson_unit_id, cardinality, asset_type
          INTO slot_organization, slot_project, slot_lesson, slot_cardinality, slot_asset_type
          FROM project_asset_slots
          WHERE id = NEW.project_asset_slot_id AND deleted_at IS NULL;
          IF slot_organization IS NULL OR slot_organization <> NEW.organization_id THEN
            RAISE EXCEPTION 'asset binding organization does not match slot';
          END IF;
          IF (slot_cardinality = 'one' AND NEW.position <> 0)
             OR (slot_cardinality = 'many' AND NEW.position <= 0) THEN
            RAISE EXCEPTION 'asset binding position does not match slot cardinality';
          END IF;

          SELECT file_asset_versions.organization_id, file_assets.asset_kind
          INTO file_organization, file_asset_type
          FROM file_asset_versions
          JOIN file_assets ON file_assets.id = file_asset_versions.file_asset_id
          WHERE file_asset_versions.id = NEW.file_asset_version_id
            AND file_assets.deleted_at IS NULL;
          IF file_organization IS NULL
             OR file_organization <> NEW.organization_id
             OR file_asset_type <> slot_asset_type THEN
            RAISE EXCEPTION 'asset binding file does not match slot contract';
          END IF;

          IF NEW.source_artifact_version_id IS NOT NULL THEN
            SELECT artifact_versions.organization_id, artifacts.project_id, artifacts.lesson_unit_id
            INTO source_organization, source_project, source_lesson
            FROM artifact_versions
            JOIN artifacts ON artifacts.id = artifact_versions.artifact_id
            WHERE artifact_versions.id = NEW.source_artifact_version_id
              AND artifacts.deleted_at IS NULL;
            IF source_organization IS NULL
               OR source_organization <> NEW.organization_id
               OR source_project <> slot_project
               OR source_lesson IS DISTINCT FROM slot_lesson THEN
              RAISE EXCEPTION 'asset binding source artifact does not match slot';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_asset_binding_scope
        BEFORE INSERT OR UPDATE ON asset_bindings
        FOR EACH ROW EXECUTE FUNCTION validate_asset_binding_scope();
        """
    )
    op.execute(
        """
        CREATE FUNCTION protect_asset_binding_history() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'asset binding history cannot be deleted';
          END IF;
          IF NOT OLD.is_active THEN
            RAISE EXCEPTION 'inactive asset bindings are immutable';
          END IF;
          IF NEW.is_active
             OR NEW.unbound_at IS NULL
             OR NEW.unbound_by IS NULL
             OR NEW.id IS DISTINCT FROM OLD.id
             OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.project_asset_slot_id IS DISTINCT FROM OLD.project_asset_slot_id
             OR NEW.file_asset_version_id IS DISTINCT FROM OLD.file_asset_version_id
             OR NEW.source_generation_result_id IS DISTINCT FROM OLD.source_generation_result_id
             OR NEW.source_artifact_version_id IS DISTINCT FROM OLD.source_artifact_version_id
             OR NEW.save_operation_id IS DISTINCT FROM OLD.save_operation_id
             OR NEW.position IS DISTINCT FROM OLD.position
             OR NEW.bound_at IS DISTINCT FROM OLD.bound_at
             OR NEW.bound_by IS DISTINCT FROM OLD.bound_by THEN
            RAISE EXCEPTION 'asset binding identity is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_asset_binding_history
        BEFORE UPDATE OR DELETE ON asset_bindings
        FOR EACH ROW EXECUTE FUNCTION protect_asset_binding_history();
        """
    )


def _drop_scope_and_history_triggers() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_asset_binding_history ON asset_bindings;
        DROP FUNCTION IF EXISTS protect_asset_binding_history();
        DROP TRIGGER IF EXISTS trg_asset_binding_scope ON asset_bindings;
        DROP FUNCTION IF EXISTS validate_asset_binding_scope();
        DROP TRIGGER IF EXISTS trg_project_asset_slot_scope ON project_asset_slots;
        DROP FUNCTION IF EXISTS validate_project_asset_slot_scope();
        """
    )
