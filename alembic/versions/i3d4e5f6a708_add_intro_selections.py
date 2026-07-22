"""Add immutable Intro selection facts."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "i3d4e5f6a708"
down_revision: str | Sequence[str] | None = "h2c3d4e5f607"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCOPE_FUNCTION = "validate_intro_selection_scope"
_SCOPE_TRIGGER = "trg_intro_selections_scope"
_MUTATION_FUNCTION = "guard_intro_selection_mutation"
_MUTATION_TRIGGER = "trg_intro_selections_guard_mutation"


def upgrade() -> None:
    op.create_table(
        "intro_selections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_unit_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_approval_id", sa.Uuid(), nullable=False),
        sa.Column("selection_method", sa.String(length=30), nullable=False),
        sa.Column("option_key", sa.String(length=80), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "policy_evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "recommendation_evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "selection_method IN ('teacher_selected', 'policy_default')",
            name="ck_intro_selections_selection_method_allowed",
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system')",
            name="ck_intro_selections_actor_type_allowed",
        ),
        sa.CheckConstraint(
            "(selection_method = 'teacher_selected' AND actor_type = 'user' "
            "AND actor_user_id IS NOT NULL) OR "
            "(selection_method = 'policy_default' AND actor_type = 'system' "
            "AND actor_user_id IS NULL)",
            name="ck_intro_selections_method_actor_consistent",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) > 0",
            name="ck_intro_selections_reason_nonempty",
        ),
        sa.CheckConstraint(
            "(active AND deactivated_at IS NULL AND deactivated_by IS NULL) OR "
            "(NOT active AND deactivated_at IS NOT NULL AND deactivated_by IS NOT NULL)",
            name="ck_intro_selections_active_deactivation_consistent",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lesson_unit_id"], ["lesson_units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["artifact_version_id"], ["artifact_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["source_approval_id"], ["approvals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deactivated_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_intro_selections_lesson_active",
        "intro_selections",
        ["organization_id", "lesson_unit_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_index(
        "ix_intro_selections_project_lesson_selected",
        "intro_selections",
        ["organization_id", "project_id", "lesson_unit_id", "selected_at"],
    )
    _create_scope_trigger()
    _create_mutation_trigger()


def _create_scope_trigger() -> None:
    op.execute(
        f"""
        CREATE FUNCTION {_SCOPE_FUNCTION}() RETURNS trigger AS $$
        DECLARE
          source_org uuid;
          source_project uuid;
          source_lesson uuid;
          source_key text;
          source_type text;
          source_status text;
          source_current uuid;
          lesson_org uuid;
          lesson_project uuid;
          lesson_stable_key text;
          approval_org uuid;
          approval_version uuid;
          approval_action text;
          latest_approval uuid;
        BEGIN
          SELECT av.organization_id, a.project_id, a.lesson_unit_id, a.artifact_key,
                 a.artifact_type, a.status, a.current_approved_version_id
            INTO source_org, source_project, source_lesson, source_key,
                 source_type, source_status, source_current
            FROM artifact_versions av JOIN artifacts a ON a.id = av.artifact_id
           WHERE av.id = NEW.artifact_version_id AND a.deleted_at IS NULL;
          SELECT lu.organization_id, lu.project_id, lu.lesson_key
            INTO lesson_org, lesson_project, lesson_stable_key
            FROM lesson_units lu WHERE lu.id = NEW.lesson_unit_id AND lu.status = 'active'
              AND lu.deleted_at IS NULL;
          SELECT organization_id, artifact_version_id, action
            INTO approval_org, approval_version, approval_action
            FROM approvals WHERE id = NEW.source_approval_id;
          SELECT id INTO latest_approval FROM approvals
           WHERE artifact_version_id = NEW.artifact_version_id
             AND organization_id = NEW.organization_id
           ORDER BY created_at DESC, id DESC LIMIT 1;
          IF source_org IS NULL OR lesson_org IS NULL OR approval_org IS NULL
             OR source_org IS DISTINCT FROM NEW.organization_id
             OR lesson_org IS DISTINCT FROM NEW.organization_id
             OR approval_org IS DISTINCT FROM NEW.organization_id
             OR source_project IS DISTINCT FROM NEW.project_id
             OR lesson_project IS DISTINCT FROM NEW.project_id
             OR source_lesson IS DISTINCT FROM NEW.lesson_unit_id
             OR source_type IS DISTINCT FROM 'intro_option_set'
             OR source_key IS DISTINCT FROM ('intro-options:' || lesson_stable_key)
             OR source_status IS DISTINCT FROM 'approved'
             OR source_current IS DISTINCT FROM NEW.artifact_version_id
             OR approval_version IS DISTINCT FROM NEW.artifact_version_id
             OR approval_action NOT IN ('approve', 'accept_stale')
             OR latest_approval IS DISTINCT FROM NEW.source_approval_id
             OR NEW.snapshot_json ->> 'option_key' IS DISTINCT FROM NEW.option_key
             OR NEW.snapshot_json ->> 'lesson_unit_key' IS DISTINCT FROM lesson_stable_key THEN
            RAISE EXCEPTION USING
              ERRCODE = '23514',
              MESSAGE = 'intro selection scope does not match its exact approved facts';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER {_SCOPE_TRIGGER}
        BEFORE INSERT ON intro_selections
        FOR EACH ROW EXECUTE FUNCTION {_SCOPE_FUNCTION}();
        """
    )


def _create_mutation_trigger() -> None:
    op.execute(
        f"""
        CREATE FUNCTION {_MUTATION_FUNCTION}() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'intro selections cannot be deleted';
          END IF;
          IF NOT OLD.active OR NEW.active OR NEW.deactivated_at IS NULL
             OR NEW.deactivated_by IS NULL
             OR (to_jsonb(NEW) - ARRAY['active', 'deactivated_at', 'deactivated_by'])
                IS DISTINCT FROM
                (to_jsonb(OLD) - ARRAY['active', 'deactivated_at', 'deactivated_by']) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'intro selection facts are immutable except one-way deactivation';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER {_MUTATION_TRIGGER}
        BEFORE UPDATE OR DELETE ON intro_selections
        FOR EACH ROW EXECUTE FUNCTION {_MUTATION_FUNCTION}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_MUTATION_TRIGGER} ON intro_selections")
    op.execute(f"DROP FUNCTION IF EXISTS {_MUTATION_FUNCTION}()")
    op.execute(f"DROP TRIGGER IF EXISTS {_SCOPE_TRIGGER} ON intro_selections")
    op.execute(f"DROP FUNCTION IF EXISTS {_SCOPE_FUNCTION}()")
    op.drop_index(
        "ix_intro_selections_project_lesson_selected",
        table_name="intro_selections",
    )
    op.drop_index("uq_intro_selections_lesson_active", table_name="intro_selections")
    op.drop_table("intro_selections")
