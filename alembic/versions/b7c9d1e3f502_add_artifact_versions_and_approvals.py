"""Add artifact drafts, immutable versions, approvals, and relations.

Revision ID: b7c9d1e3f502
Revises: a1b2c3d4e501
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7c9d1e3f502"
down_revision: str | Sequence[str] | None = "a1b2c3d4e501"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_artifacts()
    _create_artifact_versions()
    _create_artifact_drafts()
    _create_approvals()
    _create_artifact_relations()
    _add_current_pointer_constraints()
    _create_integrity_triggers()


def downgrade() -> None:
    _drop_integrity_triggers()
    op.drop_constraint("fk_node_runs_active_artifact_version", "node_runs", type_="foreignkey")
    op.drop_constraint("fk_artifacts_current_approved_version", "artifacts", type_="foreignkey")
    op.drop_constraint("fk_artifacts_current_submitted_version", "artifacts", type_="foreignkey")
    op.drop_constraint("fk_artifacts_current_draft", "artifacts", type_="foreignkey")
    op.drop_index("ix_artifact_relations_organization_from", table_name="artifact_relations")
    op.drop_index("uq_artifact_relations_versions_binding", table_name="artifact_relations")
    op.drop_table("artifact_relations")
    op.drop_index("ix_approvals_organization_version_created", table_name="approvals")
    op.drop_table("approvals")
    op.drop_index("ix_artifact_drafts_organization_artifact", table_name="artifact_drafts")
    op.drop_index("uq_artifact_drafts_artifact_branch_active", table_name="artifact_drafts")
    op.drop_table("artifact_drafts")
    op.drop_index(
        "ix_artifact_versions_organization_artifact_created",
        table_name="artifact_versions",
    )
    op.drop_index("uq_artifact_versions_artifact_version", table_name="artifact_versions")
    op.drop_table("artifact_versions")
    op.drop_index("ix_artifacts_organization_project_branch", table_name="artifacts")
    op.drop_index("uq_artifacts_project_key_active", table_name="artifacts")
    op.drop_table("artifacts")


def _create_artifacts() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_unit_id", sa.Uuid(), nullable=True),
        sa.Column("branch_key", sa.String(length=80), nullable=False),
        sa.Column("artifact_key", sa.String(length=160), nullable=False),
        sa.Column("artifact_type", sa.String(length=80), nullable=False),
        sa.Column("content_definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("current_draft_id", sa.Uuid(), nullable=True),
        sa.Column("current_submitted_version_id", sa.Uuid(), nullable=True),
        sa.Column("current_approved_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("stale_reason_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'stale', 'archived')",
            name="ck_artifacts_status_allowed",
        ),
        sa.CheckConstraint("lock_version >= 1", name="ck_artifacts_lock_version_positive"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_artifacts_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_artifacts_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_unit_id"],
            ["lesson_units.id"],
            name="fk_artifacts_lesson_unit_id_lesson_units",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["content_definition_version_id"],
            ["content_definition_versions.id"],
            name="fk_artifacts_content_definition_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["principals.id"],
            name="fk_artifacts_created_by_principals",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["principals.id"],
            name="fk_artifacts_updated_by_principals",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifacts"),
    )
    op.create_index(
        "uq_artifacts_project_key_active",
        "artifacts",
        ["project_id", "artifact_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_artifacts_organization_project_branch",
        "artifacts",
        ["organization_id", "project_id", "lesson_unit_id", "branch_key"],
    )


def _create_artifact_versions() -> None:
    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content_json", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("render_summary_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_kind", sa.String(length=20), nullable=False),
        sa.Column("source_node_run_id", sa.Uuid(), nullable=True),
        sa.Column("context_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("prompt_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("validation_report_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint("version_no > 0", name="ck_artifact_versions_version_positive"),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_artifact_versions_content_hash_format",
        ),
        sa.CheckConstraint(
            "source_kind IN ('manual', 'model', 'import', 'system')",
            name="ck_artifact_versions_source_kind_allowed",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_node_run_id"], ["node_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_artifact_versions"),
    )
    op.create_index(
        "uq_artifact_versions_artifact_version",
        "artifact_versions",
        ["artifact_id", "version_no"],
        unique=True,
    )
    op.create_index(
        "ix_artifact_versions_organization_artifact_created",
        "artifact_versions",
        ["organization_id", "artifact_id", "created_at"],
    )


def _create_artifact_drafts() -> None:
    op.create_table(
        "artifact_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("draft_branch", sa.String(length=80), nullable=False),
        sa.Column("content_json", postgresql.JSONB(), nullable=False),
        sa.Column("validation_report_json", postgresql.JSONB(), nullable=False),
        sa.Column("based_on_version_id", sa.Uuid(), nullable=True),
        sa.Column("autosaved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("lock_version >= 1", name="ck_artifact_drafts_lock_version_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["based_on_version_id"], ["artifact_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_artifact_drafts"),
    )
    op.create_index(
        "uq_artifact_drafts_artifact_branch_active",
        "artifact_drafts",
        ["artifact_id", "draft_branch"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_artifact_drafts_organization_artifact",
        "artifact_drafts",
        ["organization_id", "artifact_id"],
    )


def _create_approvals() -> None:
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_version_id", sa.Uuid(), nullable=False),
        sa.Column("node_run_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("quality_evidence_json", postgresql.JSONB(), nullable=False),
        sa.Column("policy_snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "action IN ('submit', 'approve', 'request_changes', 'revoke', 'accept_stale')",
            name="ck_approvals_action_allowed",
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system')", name="ck_approvals_actor_type_allowed"
        ),
        sa.CheckConstraint(
            "(actor_type = 'system' AND actor_user_id IS NULL) OR "
            "(actor_type = 'user' AND actor_user_id IS NOT NULL)",
            name="ck_approvals_actor_user_link",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["artifact_version_id"], ["artifact_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["node_run_id"], ["node_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_approvals"),
    )
    op.create_index(
        "ix_approvals_organization_version_created",
        "approvals",
        ["organization_id", "artifact_version_id", "created_at"],
    )


def _create_artifact_relations() -> None:
    op.create_table(
        "artifact_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("from_artifact_version_id", sa.Uuid(), nullable=False),
        sa.Column("to_artifact_version_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=30), nullable=False),
        sa.Column("binding_key", sa.String(length=160), nullable=False),
        sa.Column("impact_scope_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "relation_type IN ('derives_from', 'references', 'constrains', 'supersedes')",
            name="ck_artifact_relations_relation_type_allowed",
        ),
        sa.CheckConstraint(
            "from_artifact_version_id <> to_artifact_version_id",
            name="ck_artifact_relations_no_self_relation",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["from_artifact_version_id"], ["artifact_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["to_artifact_version_id"], ["artifact_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_artifact_relations"),
    )
    op.create_index(
        "uq_artifact_relations_versions_binding",
        "artifact_relations",
        [
            "from_artifact_version_id",
            "to_artifact_version_id",
            "relation_type",
            "binding_key",
        ],
        unique=True,
    )
    op.create_index(
        "ix_artifact_relations_organization_from",
        "artifact_relations",
        ["organization_id", "from_artifact_version_id"],
    )


def _add_current_pointer_constraints() -> None:
    op.create_foreign_key(
        "fk_artifacts_current_draft",
        "artifacts",
        "artifact_drafts",
        ["current_draft_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_artifacts_current_submitted_version",
        "artifacts",
        "artifact_versions",
        ["current_submitted_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_artifacts_current_approved_version",
        "artifacts",
        "artifact_versions",
        ["current_approved_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_node_runs_active_artifact_version",
        "node_runs",
        "artifact_versions",
        ["active_artifact_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def _create_integrity_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION validate_artifact_current_refs() RETURNS trigger AS $$
        BEGIN
          IF NEW.current_draft_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM artifact_drafts
            WHERE id = NEW.current_draft_id AND artifact_id = NEW.id
          ) THEN
            RAISE EXCEPTION 'current draft must belong to artifact';
          END IF;
          IF NEW.current_submitted_version_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM artifact_versions
            WHERE id = NEW.current_submitted_version_id AND artifact_id = NEW.id
          ) THEN
            RAISE EXCEPTION 'current submitted version must belong to artifact';
          END IF;
          IF NEW.current_approved_version_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM artifact_versions
            WHERE id = NEW.current_approved_version_id AND artifact_id = NEW.id
          ) THEN
            RAISE EXCEPTION 'current approved version must belong to artifact';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_artifacts_validate_current_refs
        BEFORE INSERT OR UPDATE OF current_draft_id,
          current_submitted_version_id, current_approved_version_id
        ON artifacts FOR EACH ROW EXECUTE FUNCTION validate_artifact_current_refs();

        CREATE FUNCTION reject_artifact_history_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION '% rows are append-only', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_artifact_versions_append_only
        BEFORE UPDATE OR DELETE ON artifact_versions
        FOR EACH ROW EXECUTE FUNCTION reject_artifact_history_mutation();

        CREATE TRIGGER trg_approvals_append_only
        BEFORE UPDATE OR DELETE ON approvals
        FOR EACH ROW EXECUTE FUNCTION reject_artifact_history_mutation();
        """
    )


def _drop_integrity_triggers() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_approvals_append_only ON approvals")
    op.execute("DROP TRIGGER IF EXISTS trg_artifact_versions_append_only ON artifact_versions")
    op.execute("DROP FUNCTION IF EXISTS reject_artifact_history_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_artifacts_validate_current_refs ON artifacts")
    op.execute("DROP FUNCTION IF EXISTS validate_artifact_current_refs()")
