"""Allow the exact approved Intro version while a revision is in review."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "j4e5f6a7b809"
down_revision: str | Sequence[str] | None = "i3d4e5f6a708"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCOPE_FUNCTION = "validate_intro_selection_scope"


def upgrade() -> None:
    _replace_scope_function("source_status IN ('stale', 'archived')")


def downgrade() -> None:
    _replace_scope_function("source_status IS DISTINCT FROM 'approved'")


def _replace_scope_function(status_rejected: str) -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {_SCOPE_FUNCTION}() RETURNS trigger AS $$
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
             OR {status_rejected}
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
        """
    )
