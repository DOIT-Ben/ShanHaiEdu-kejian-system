"""Add immutable artifact quality reports."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "h2c3d4e5f607"
down_revision: str | Sequence[str] | None = "g1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABILITY_FUNCTION = "reject_artifact_quality_report_mutation"
_IMMUTABILITY_TRIGGER = "trg_artifact_quality_reports_immutable"
_SCOPE_FUNCTION = "validate_artifact_quality_report_scope"
_SCOPE_TRIGGER = "trg_artifact_quality_reports_scope"


def upgrade() -> None:
    op.create_table(
        "artifact_quality_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_unit_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_artifact_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_file_asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_release_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("validate_node_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "validator_set_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("validator_set_hash", sa.String(length=64), nullable=False),
        sa.Column("conclusion", sa.String(length=20), nullable=False),
        sa.Column(
            "findings_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "source_content_hash ~ '^[0-9a-f]{64}$'",
            name="source_content_hash_format",
        ),
        sa.CheckConstraint(
            "(source_type = 'artifact' AND source_artifact_version_id IS NOT NULL "
            "AND source_file_asset_version_id IS NULL) OR "
            "(source_type = 'asset' AND source_artifact_version_id IS NULL "
            "AND source_file_asset_version_id IS NOT NULL)",
            name="source_identity_exactly_one",
        ),
        sa.CheckConstraint(
            "validator_set_hash ~ '^[0-9a-f]{64}$'",
            name="validator_set_hash_format",
        ),
        sa.CheckConstraint(
            "evidence_hash ~ '^[0-9a-f]{64}$'",
            name="evidence_hash_format",
        ),
        sa.CheckConstraint(
            "conclusion IN ('passed', 'failed')",
            name="conclusion_allowed",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(validator_set_json) = 'array' "
            "AND jsonb_array_length(validator_set_json) > 0",
            name="validator_set_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(findings_json) = 'array'",
            name="findings_array",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_artifact_quality_reports_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_artifact_quality_reports_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_unit_id"],
            ["lesson_units.id"],
            name="fk_artifact_quality_reports_lesson_unit",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_version_id"],
            ["artifact_versions.id"],
            name="fk_artifact_quality_reports_source_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_file_asset_version_id"],
            ["file_asset_versions.id"],
            name="fk_artifact_quality_reports_source_file_asset_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["content_release_id"],
            ["content_releases.id"],
            name="fk_artifact_quality_reports_content_release",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_definition_version_id"],
            ["workflow_definition_versions.id"],
            name="fk_artifact_quality_reports_workflow_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validate_node_run_id"],
            ["node_runs.id"],
            name="fk_artifact_quality_reports_validate_node_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["principals.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_artifact_quality_reports_source_workflow_validators",
        "artifact_quality_reports",
        [
            "source_artifact_version_id",
            "workflow_definition_version_id",
            "validator_set_hash",
        ],
        unique=True,
        postgresql_where=sa.text("source_type = 'artifact'"),
    )
    op.create_index(
        "uq_artifact_quality_reports_asset_source_workflow_validators",
        "artifact_quality_reports",
        [
            "source_file_asset_version_id",
            "workflow_definition_version_id",
            "validator_set_hash",
        ],
        unique=True,
        postgresql_where=sa.text("source_type = 'asset'"),
    )
    op.create_index(
        "uq_artifact_quality_reports_validate_node_run",
        "artifact_quality_reports",
        ["validate_node_run_id"],
        unique=True,
    )
    op.create_index(
        "ix_artifact_quality_reports_project_source",
        "artifact_quality_reports",
        [
            "organization_id",
            "project_id",
            "source_type",
            "source_artifact_version_id",
            "source_file_asset_version_id",
        ],
    )
    op.execute(
        f"""
        CREATE FUNCTION {_SCOPE_FUNCTION}() RETURNS trigger AS $$
        DECLARE
          source_version_organization uuid;
          source_parent_organization uuid;
          source_record_id uuid;
          fixed_source_version_id uuid;
          source_project uuid;
          source_lesson uuid;
          source_hash text;
          node_organization uuid;
          run_organization uuid;
          node_project uuid;
          node_lesson uuid;
          node_release uuid;
          node_workflow uuid;
          source_binding_matches boolean;
          declared_validator_set jsonb;
          declared_validator_payload text;
        BEGIN
          IF NEW.source_type = 'artifact' THEN
            fixed_source_version_id := NEW.source_artifact_version_id;
            SELECT artifact_versions.organization_id,
                   artifacts.organization_id,
                   artifacts.id,
                   artifacts.project_id,
                   artifacts.lesson_unit_id,
                   artifact_versions.content_hash
            INTO source_version_organization,
                 source_parent_organization,
                 source_record_id,
                 source_project,
                 source_lesson,
                 source_hash
            FROM artifact_versions
            JOIN artifacts ON artifacts.id = artifact_versions.artifact_id
            WHERE artifact_versions.id = fixed_source_version_id;
          ELSIF NEW.source_type = 'asset' THEN
            fixed_source_version_id := NEW.source_file_asset_version_id;
            SELECT file_asset_versions.organization_id,
                   file_assets.organization_id,
                   file_assets.id,
                   file_asset_versions.sha256
            INTO source_version_organization,
                 source_parent_organization,
                 source_record_id,
                 source_hash
            FROM file_asset_versions
            JOIN file_assets ON file_assets.id = file_asset_versions.file_asset_id
            WHERE file_asset_versions.id = fixed_source_version_id;
          ELSE
            RAISE EXCEPTION USING
              ERRCODE = '23514',
              MESSAGE = 'artifact quality report source type is invalid';
          END IF;

          SELECT node_runs.organization_id,
                 workflow_runs.organization_id,
                 workflow_runs.project_id,
                 branch_runs.lesson_unit_id,
                 workflow_runs.content_release_id,
                 workflow_runs.workflow_definition_version_id
          INTO node_organization,
               run_organization,
               node_project,
               node_lesson,
               node_release,
               node_workflow
          FROM node_runs
          JOIN workflow_runs ON workflow_runs.id = node_runs.workflow_run_id
          LEFT JOIN branch_runs ON branch_runs.id = node_runs.branch_run_id
          WHERE node_runs.id = NEW.validate_node_run_id;

          SELECT node_input_snapshots.id IS NOT NULL,
                 (
                   SELECT jsonb_agg(
                            validator_ref.value
                            ORDER BY validator_ref.value->>'key',
                                     validator_ref.value->>'semantic_version',
                                     validator_ref.value->>'implementation_digest'
                          )
                   FROM jsonb_array_elements(
                     node_definition.value
                       ->'quality_report_persistence'
                       ->'validator_refs'
                   ) AS validator_ref(value)
                 ),
                 (
                   SELECT '[' || string_agg(
                            '{{"implementation_digest":' ||
                            to_jsonb(validator_ref.value->>'implementation_digest')::text ||
                            ',"key":' || to_jsonb(validator_ref.value->>'key')::text ||
                            ',"semantic_version":' ||
                            to_jsonb(validator_ref.value->>'semantic_version')::text || '}}',
                            ','
                            ORDER BY validator_ref.value->>'key',
                                     validator_ref.value->>'semantic_version',
                                     validator_ref.value->>'implementation_digest'
                          ) || ']'
                   FROM jsonb_array_elements(
                     node_definition.value
                       ->'quality_report_persistence'
                       ->'validator_refs'
                   ) AS validator_ref(value)
                 )
          INTO source_binding_matches,
               declared_validator_set,
               declared_validator_payload
          FROM node_runs
          JOIN workflow_runs ON workflow_runs.id = node_runs.workflow_run_id
          JOIN workflow_definition_versions
            ON workflow_definition_versions.id = workflow_runs.workflow_definition_version_id
          CROSS JOIN LATERAL jsonb_array_elements(
            workflow_definition_versions.graph_json->'nodes'
          ) AS node_definition(value)
          LEFT JOIN node_input_snapshots
            ON node_input_snapshots.node_run_id = node_runs.id
           AND node_input_snapshots.input_key = (
             node_definition.value
               ->'quality_report_persistence'
               ->>'source_input_ref'
           )
           AND node_input_snapshots.source_type = NEW.source_type
           AND node_input_snapshots.source_id = source_record_id
           AND node_input_snapshots.source_version_id = fixed_source_version_id
           AND node_input_snapshots.content_hash = NEW.source_content_hash
          WHERE node_runs.id = NEW.validate_node_run_id
            AND node_definition.value->>'node_key' = node_runs.node_key
          LIMIT 1;

          IF source_version_organization IS NULL
             OR node_organization IS NULL
             OR source_binding_matches IS DISTINCT FROM TRUE
             OR NEW.validator_set_json IS DISTINCT FROM declared_validator_set
             OR NEW.validator_set_hash IS DISTINCT FROM encode(
               sha256(convert_to(declared_validator_payload, 'UTF8')),
               'hex'
             )
             OR NEW.organization_id IS DISTINCT FROM source_version_organization
             OR NEW.organization_id IS DISTINCT FROM source_parent_organization
             OR NEW.organization_id IS DISTINCT FROM node_organization
             OR NEW.organization_id IS DISTINCT FROM run_organization
             OR (
               NEW.source_type = 'artifact'
               AND NEW.project_id IS DISTINCT FROM source_project
             )
             OR NEW.project_id IS DISTINCT FROM node_project
             OR (
               NEW.source_type = 'artifact'
               AND NEW.lesson_unit_id IS DISTINCT FROM source_lesson
             )
             OR NEW.lesson_unit_id IS DISTINCT FROM node_lesson
             OR NEW.source_content_hash IS DISTINCT FROM source_hash
             OR NEW.content_release_id IS DISTINCT FROM node_release
             OR NEW.workflow_definition_version_id IS DISTINCT FROM node_workflow THEN
            RAISE EXCEPTION USING
              ERRCODE = '23514',
              MESSAGE = 'artifact quality report scope does not match its fixed facts';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER {_SCOPE_TRIGGER}
        BEFORE INSERT ON artifact_quality_reports
        FOR EACH ROW EXECUTE FUNCTION {_SCOPE_FUNCTION}();

        CREATE FUNCTION {_IMMUTABILITY_FUNCTION}() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'artifact quality reports are append-only';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER {_IMMUTABILITY_TRIGGER}
        BEFORE UPDATE OR DELETE ON artifact_quality_reports
        FOR EACH ROW EXECUTE FUNCTION {_IMMUTABILITY_FUNCTION}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_IMMUTABILITY_TRIGGER} ON artifact_quality_reports")
    op.execute(f"DROP FUNCTION IF EXISTS {_IMMUTABILITY_FUNCTION}()")
    op.execute(f"DROP TRIGGER IF EXISTS {_SCOPE_TRIGGER} ON artifact_quality_reports")
    op.execute(f"DROP FUNCTION IF EXISTS {_SCOPE_FUNCTION}()")
    op.drop_index(
        "ix_artifact_quality_reports_project_source",
        table_name="artifact_quality_reports",
    )
    op.drop_index(
        "uq_artifact_quality_reports_validate_node_run",
        table_name="artifact_quality_reports",
    )
    op.drop_index(
        "uq_artifact_quality_reports_asset_source_workflow_validators",
        table_name="artifact_quality_reports",
    )
    op.drop_index(
        "uq_artifact_quality_reports_source_workflow_validators",
        table_name="artifact_quality_reports",
    )
    op.drop_table("artifact_quality_reports")
