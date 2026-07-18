"""Add versioned automation policy and creation lifecycle runtime.

Revision ID: d2e5f8a1c604
Revises: b4a7c2d9e805
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d2e5f8a1c604"
down_revision: str | Sequence[str] | None = "b4a7c2d9e805"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_automation_policies()
    _backfill_automation_policies()
    _create_creation_packages()
    _create_creation_batches_and_items()
    _create_prompt_results_and_adoptions()
    _extend_generation_jobs()
    _create_save_operations()
    _link_creation_foreign_keys()
    _create_creation_scope_triggers()
    _create_immutable_fact_triggers()


def downgrade() -> None:
    _drop_immutable_fact_triggers()
    _drop_creation_scope_triggers()
    op.drop_constraint("fk_asset_bindings_save_operation", "asset_bindings", type_="foreignkey")
    op.drop_constraint("fk_asset_bindings_generation_result", "asset_bindings", type_="foreignkey")
    op.drop_constraint("fk_creation_items_active_adoption", "creation_items", type_="foreignkey")
    op.drop_constraint(
        "fk_creation_items_current_prompt_version", "creation_items", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_save_operations_created_binding",
        "save_to_project_operations",
        type_="foreignkey",
    )
    op.drop_table("save_to_project_operations")
    _restore_generation_jobs()
    op.drop_index("ix_adoptions_organization_item", table_name="adoptions")
    op.drop_table("adoptions")
    op.drop_index("uq_generation_results_job_candidate", table_name="generation_results")
    op.drop_table("generation_results")
    op.drop_index(
        "uq_creation_prompt_versions_item_version",
        table_name="creation_prompt_versions",
    )
    op.drop_table("creation_prompt_versions")
    op.drop_index("uq_creation_items_batch_key", table_name="creation_items")
    op.drop_table("creation_items")
    op.drop_index("ix_creation_batches_organization_created", table_name="creation_batches")
    op.drop_table("creation_batches")
    op.drop_index(
        "uq_creation_package_items_package_position",
        table_name="creation_package_items",
    )
    op.drop_index("uq_creation_package_items_package_key", table_name="creation_package_items")
    op.drop_table("creation_package_items")
    op.drop_index("ix_creation_packages_organization_project_node", table_name="creation_packages")
    op.drop_index("uq_creation_packages_package_key", table_name="creation_packages")
    op.drop_table("creation_packages")
    op.drop_index(
        "ix_project_automation_policies_organization_project",
        table_name="project_automation_policies",
    )
    op.drop_index(
        "uq_project_automation_policies_project_version",
        table_name="project_automation_policies",
    )
    op.drop_table("project_automation_policies")


def _create_automation_policies() -> None:
    op.create_table(
        "project_automation_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("node_rules_json", postgresql.JSONB(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "mode IN ('guided', 'automatic')",
            name="ck_project_automation_policies_mode_allowed",
        ),
        sa.CheckConstraint(
            "policy_version > 0",
            name="ck_project_automation_policies_policy_version_positive",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["workflow_definition_version_id"],
            ["workflow_definition_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_project_automation_policies"),
    )
    op.create_index(
        "uq_project_automation_policies_project_version",
        "project_automation_policies",
        ["project_id", "policy_version"],
        unique=True,
    )
    op.create_index(
        "ix_project_automation_policies_organization_project",
        "project_automation_policies",
        ["organization_id", "project_id"],
    )


def _backfill_automation_policies() -> None:
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO project_automation_policies (
          id, organization_id, project_id, workflow_definition_version_id,
          mode, node_rules_json, policy_version, created_at, created_by
        )
        SELECT
          md5(projects.id::text || ':automation-policy:1')::uuid,
          projects.organization_id,
          projects.id,
          projects.workflow_definition_version_id,
          CASE WHEN projects.automation_mode = 'automatic' THEN 'automatic' ELSE 'guided' END,
          CASE WHEN projects.automation_mode = 'manual' THEN
            '[{"node_key":"*","auto_start":false,"auto_submit":false,'
            '"auto_approve":false,"auto_adopt":false,'
            '"auto_save_to_project":false,"pause_after":true}]'::jsonb
          ELSE '[]'::jsonb END,
          1,
          projects.updated_at,
          projects.updated_by
        FROM projects
        WHERE projects.workflow_definition_version_id IS NOT NULL
        """
    )


def _create_creation_packages() -> None:
    op.create_table(
        "creation_packages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("package_key", sa.String(length=180), nullable=False),
        sa.Column("source_project_id", sa.Uuid(), nullable=False),
        sa.Column("source_workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("source_node_run_id", sa.Uuid(), nullable=False),
        sa.Column("context_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("source_prompt_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("package_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("target_rules_json", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_stale_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "package_type IN ('image', 'video', 'presentation')",
            name="ck_creation_packages_package_type_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('building', 'ready', 'invalid', 'expired')",
            name="ck_creation_packages_status_allowed",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_creation_packages_content_hash_format",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_workflow_run_id"], ["workflow_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["source_node_run_id"], ["node_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["context_snapshot_id"], ["context_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_prompt_snapshot_id"], ["prompt_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_creation_packages"),
    )
    op.create_index(
        "uq_creation_packages_package_key",
        "creation_packages",
        ["package_key"],
        unique=True,
    )
    op.create_index(
        "ix_creation_packages_organization_project_node",
        "creation_packages",
        ["organization_id", "source_project_id", "source_node_run_id"],
    )
    op.create_table(
        "creation_package_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creation_package_id", sa.Uuid(), nullable=False),
        sa.Column("item_key", sa.String(length=160), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("business_prompt", sa.Text(), nullable=False),
        sa.Column("prompt_json", postgresql.JSONB(), nullable=False),
        sa.Column("reference_asset_version_ids", postgresql.JSONB(), nullable=False),
        sa.Column("output_spec_json", postgresql.JSONB(), nullable=False),
        sa.Column("target_slot_key", sa.String(length=160), nullable=False),
        sa.Column("consistency_key", sa.String(length=160), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint("position > 0", name="ck_creation_package_items_position_positive"),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_creation_package_items_content_hash_format",
        ),
        sa.ForeignKeyConstraint(
            ["creation_package_id"], ["creation_packages.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_creation_package_items"),
    )
    op.create_index(
        "uq_creation_package_items_package_key",
        "creation_package_items",
        ["creation_package_id", "item_key"],
        unique=True,
    )
    op.create_index(
        "uq_creation_package_items_package_position",
        "creation_package_items",
        ["creation_package_id", "position"],
        unique=True,
    )


def _mutable_audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _audit_foreign_keys() -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["principals.id"], ondelete="RESTRICT"),
    ]


def _create_creation_batches_and_items() -> None:
    op.create_table(
        "creation_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(length=20), nullable=False),
        sa.Column("creation_package_id", sa.Uuid(), nullable=True),
        sa.Column("source_project_id", sa.Uuid(), nullable=True),
        sa.Column("source_workflow_run_id", sa.Uuid(), nullable=True),
        sa.Column("source_node_run_id", sa.Uuid(), nullable=True),
        sa.Column("studio_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        *_mutable_audit_columns(),
        sa.CheckConstraint(
            "source_kind IN ('project', 'standalone')",
            name="ck_creation_batches_source_kind_allowed",
        ),
        sa.CheckConstraint(
            "studio_type IN ('image', 'video', 'presentation')",
            name="ck_creation_batches_studio_type_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'running', 'partially_completed', "
            "'completed', 'archived')",
            name="ck_creation_batches_status_allowed",
        ),
        sa.CheckConstraint(
            "(source_kind = 'project' AND creation_package_id IS NOT NULL "
            "AND source_project_id IS NOT NULL AND source_workflow_run_id IS NOT NULL "
            "AND source_node_run_id IS NOT NULL) OR "
            "(source_kind = 'standalone' AND creation_package_id IS NULL "
            "AND source_project_id IS NULL AND source_workflow_run_id IS NULL "
            "AND source_node_run_id IS NULL)",
            name="ck_creation_batches_source_fields_consistent",
        ),
        sa.CheckConstraint("lock_version >= 1", name="ck_creation_batches_lock_version_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["creation_package_id"], ["creation_packages.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["source_project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_workflow_run_id"], ["workflow_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["source_node_run_id"], ["node_runs.id"], ondelete="RESTRICT"),
        *_audit_foreign_keys(),
        sa.PrimaryKeyConstraint("id", name="pk_creation_batches"),
    )
    op.create_index(
        "ix_creation_batches_organization_created",
        "creation_batches",
        ["organization_id", "created_at"],
    )
    op.create_table(
        "creation_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("creation_batch_id", sa.Uuid(), nullable=False),
        sa.Column("creation_package_item_id", sa.Uuid(), nullable=True),
        sa.Column("item_key", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("current_prompt_version_id", sa.Uuid(), nullable=True),
        sa.Column("active_adoption_id", sa.Uuid(), nullable=True),
        sa.Column("target_slot_key", sa.String(length=160), nullable=True),
        *_mutable_audit_columns(),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'generating', 'review_required', "
            "'adopted', 'saved', 'failed')",
            name="ck_creation_items_status_allowed",
        ),
        sa.CheckConstraint(
            "(creation_package_item_id IS NULL AND target_slot_key IS NULL) OR "
            "(creation_package_item_id IS NOT NULL AND target_slot_key IS NOT NULL)",
            name="ck_creation_items_package_target_consistent",
        ),
        sa.CheckConstraint("lock_version >= 1", name="ck_creation_items_lock_version_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["creation_batch_id"], ["creation_batches.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["creation_package_item_id"],
            ["creation_package_items.id"],
            ondelete="RESTRICT",
        ),
        *_audit_foreign_keys(),
        sa.PrimaryKeyConstraint("id", name="pk_creation_items"),
    )
    op.create_index(
        "uq_creation_items_batch_key",
        "creation_items",
        ["creation_batch_id", "item_key"],
        unique=True,
    )


def _create_prompt_results_and_adoptions() -> None:
    op.create_table(
        "creation_prompt_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("creation_item_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("business_prompt", sa.Text(), nullable=False),
        sa.Column("reference_asset_version_ids", postgresql.JSONB(), nullable=False),
        sa.Column("output_spec_json", postgresql.JSONB(), nullable=False),
        sa.Column("generation_profile", sa.String(length=20), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint("version_no > 0", name="ck_creation_prompt_versions_version_positive"),
        sa.CheckConstraint(
            "generation_profile IN ('quality', 'balanced', 'speed')",
            name="ck_creation_prompt_versions_generation_profile_allowed",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_creation_prompt_versions_content_hash_format",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creation_item_id"], ["creation_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_creation_prompt_versions"),
    )
    op.create_index(
        "uq_creation_prompt_versions_item_version",
        "creation_prompt_versions",
        ["creation_item_id", "version_no"],
        unique=True,
    )
    op.create_table(
        "generation_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("creation_item_id", sa.Uuid(), nullable=False),
        sa.Column("generation_job_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("file_asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("output_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("candidate_no > 0", name="ck_generation_results_candidate_positive"),
        sa.CheckConstraint(
            "status IN ('available', 'rejected', 'expired')",
            name="ck_generation_results_status_allowed",
        ),
        sa.CheckConstraint(
            "status <> 'available' OR file_asset_version_id IS NOT NULL",
            name="ck_generation_results_available_file_present",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creation_item_id"], ["creation_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["generation_job_id"], ["generation_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["file_asset_version_id"], ["file_asset_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_generation_results"),
    )
    op.create_index(
        "uq_generation_results_job_candidate",
        "generation_results",
        ["generation_job_id", "candidate_no"],
        unique=True,
    )
    op.create_table(
        "adoptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("creation_item_id", sa.Uuid(), nullable=False),
        sa.Column("generation_result_id", sa.Uuid(), nullable=False),
        sa.Column("adoption_mode", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("adopted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("adopted_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "adoption_mode IN ('teacher', 'automation_policy')",
            name="ck_adoptions_adoption_mode_allowed",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creation_item_id"], ["creation_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["generation_result_id"], ["generation_results.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["adopted_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_adoptions"),
    )
    op.create_index(
        "ix_adoptions_organization_item",
        "adoptions",
        ["organization_id", "creation_item_id"],
    )


def _extend_generation_jobs() -> None:
    op.drop_constraint(
        op.f("ck_generation_jobs_stage0_source_present"),
        "generation_jobs",
        type_="check",
    )
    op.add_column(
        "generation_jobs", sa.Column("creation_prompt_version_id", sa.Uuid(), nullable=True)
    )
    op.add_column("generation_jobs", sa.Column("creation_batch_id", sa.Uuid(), nullable=True))
    op.add_column(
        "generation_jobs",
        sa.Column("creation_request_json", postgresql.JSONB(), nullable=True),
    )
    op.create_foreign_key(
        "fk_generation_jobs_creation_prompt_version",
        "generation_jobs",
        "creation_prompt_versions",
        ["creation_prompt_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_generation_jobs_creation_batch",
        "generation_jobs",
        "creation_batches",
        ["creation_batch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "stage0_source_present",
        "generation_jobs",
        "project_id IS NOT NULL OR source_material_id IS NOT NULL "
        "OR creation_prompt_version_id IS NOT NULL OR creation_batch_id IS NOT NULL",
    )


def _restore_generation_jobs() -> None:
    op.drop_constraint(
        op.f("ck_generation_jobs_stage0_source_present"),
        "generation_jobs",
        type_="check",
    )
    op.drop_constraint("fk_generation_jobs_creation_batch", "generation_jobs", type_="foreignkey")
    op.drop_constraint(
        "fk_generation_jobs_creation_prompt_version",
        "generation_jobs",
        type_="foreignkey",
    )
    op.drop_column("generation_jobs", "creation_request_json")
    op.drop_column("generation_jobs", "creation_batch_id")
    op.drop_column("generation_jobs", "creation_prompt_version_id")
    op.create_check_constraint(
        "stage0_source_present",
        "generation_jobs",
        "project_id IS NOT NULL OR source_material_id IS NOT NULL",
    )


def _create_save_operations() -> None:
    op.create_table(
        "save_to_project_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("source_adoption_id", sa.Uuid(), nullable=False),
        sa.Column("target_project_id", sa.Uuid(), nullable=False),
        sa.Column("target_slot_key", sa.String(length=160), nullable=False),
        sa.Column("replace_mode", sa.String(length=30), nullable=False),
        sa.Column("authorization_snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_binding_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "replace_mode IN ('reject_if_occupied', 'replace_active', 'append')",
            name="ck_save_to_project_operations_replace_mode_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed')",
            name="ck_save_to_project_operations_status_allowed",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND created_binding_id IS NULL AND completed_at IS NULL) OR "
            "(status = 'completed' AND created_binding_id IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_save_to_project_operations_completion_consistent",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_adoption_id"], ["adoptions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_save_to_project_operations"),
    )
    op.create_index(
        "uq_save_to_project_operations_organization_key",
        "save_to_project_operations",
        ["organization_id", "idempotency_key"],
        unique=True,
    )


def _link_creation_foreign_keys() -> None:
    op.create_foreign_key(
        "fk_creation_items_current_prompt_version",
        "creation_items",
        "creation_prompt_versions",
        ["current_prompt_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_creation_items_active_adoption",
        "creation_items",
        "adoptions",
        ["active_adoption_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_asset_bindings_generation_result",
        "asset_bindings",
        "generation_results",
        ["source_generation_result_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_asset_bindings_save_operation",
        "asset_bindings",
        "save_to_project_operations",
        ["save_operation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_save_operations_created_binding",
        "save_to_project_operations",
        "asset_bindings",
        ["created_binding_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def _create_creation_scope_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION validate_creation_batch_scope() RETURNS trigger AS $$
        DECLARE package_record creation_packages%ROWTYPE;
        BEGIN
          IF NEW.source_kind = 'project' THEN
            SELECT * INTO package_record FROM creation_packages
            WHERE id = NEW.creation_package_id;
            IF package_record.id IS NULL
               OR package_record.organization_id <> NEW.organization_id
               OR package_record.source_project_id <> NEW.source_project_id
               OR package_record.source_workflow_run_id <> NEW.source_workflow_run_id
               OR package_record.source_node_run_id <> NEW.source_node_run_id THEN
              RAISE EXCEPTION 'creation batch source does not match package';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_creation_batch_scope
        BEFORE INSERT OR UPDATE ON creation_batches
        FOR EACH ROW EXECUTE FUNCTION validate_creation_batch_scope();

        CREATE FUNCTION validate_creation_item_scope() RETURNS trigger AS $$
        DECLARE batch_kind text; batch_package uuid; package_item creation_package_items%ROWTYPE;
        BEGIN
          SELECT source_kind, creation_package_id INTO batch_kind, batch_package
          FROM creation_batches WHERE id = NEW.creation_batch_id;
          IF batch_kind IS NULL THEN RAISE EXCEPTION 'creation item batch is missing'; END IF;
          IF batch_kind = 'project' THEN
            SELECT * INTO package_item FROM creation_package_items
            WHERE id = NEW.creation_package_item_id;
            IF package_item.id IS NULL
               OR package_item.creation_package_id <> batch_package
               OR package_item.target_slot_key <> NEW.target_slot_key THEN
              RAISE EXCEPTION 'creation item target does not match package';
            END IF;
          ELSIF NEW.creation_package_item_id IS NOT NULL OR NEW.target_slot_key IS NOT NULL THEN
            RAISE EXCEPTION 'standalone creation item cannot contain project target';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_creation_item_scope
        BEFORE INSERT OR UPDATE ON creation_items
        FOR EACH ROW EXECUTE FUNCTION validate_creation_item_scope();

        CREATE FUNCTION validate_save_operation_scope() RETURNS trigger AS $$
        DECLARE batch_kind text; source_project uuid; source_target text;
        DECLARE adoption_organization uuid; target_organization uuid; slot_id uuid;
        BEGIN
          SELECT adoptions.organization_id, creation_batches.source_kind,
                 creation_batches.source_project_id, creation_items.target_slot_key
          INTO adoption_organization, batch_kind, source_project, source_target
          FROM adoptions
          JOIN creation_items ON creation_items.id = adoptions.creation_item_id
          JOIN creation_batches ON creation_batches.id = creation_items.creation_batch_id
          WHERE adoptions.id = NEW.source_adoption_id;
          SELECT organization_id INTO target_organization FROM projects
          WHERE id = NEW.target_project_id AND deleted_at IS NULL;
          SELECT id INTO slot_id FROM project_asset_slots
          WHERE project_id = NEW.target_project_id AND slot_key = NEW.target_slot_key
            AND deleted_at IS NULL;
          IF adoption_organization IS NULL
             OR adoption_organization <> NEW.organization_id
             OR target_organization <> NEW.organization_id
             OR slot_id IS NULL THEN
            RAISE EXCEPTION 'save operation scope is invalid';
          END IF;
          IF batch_kind = 'project'
             AND (source_project <> NEW.target_project_id OR source_target <> NEW.target_slot_key)
          THEN RAISE EXCEPTION 'project save target cannot override package'; END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_save_operation_scope
        BEFORE INSERT OR UPDATE ON save_to_project_operations
        FOR EACH ROW EXECUTE FUNCTION validate_save_operation_scope();
        """
    )


def _drop_creation_scope_triggers() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_save_operation_scope ON save_to_project_operations;
        DROP FUNCTION IF EXISTS validate_save_operation_scope();
        DROP TRIGGER IF EXISTS trg_creation_item_scope ON creation_items;
        DROP FUNCTION IF EXISTS validate_creation_item_scope();
        DROP TRIGGER IF EXISTS trg_creation_batch_scope ON creation_batches;
        DROP FUNCTION IF EXISTS validate_creation_batch_scope();
        """
    )


def _create_immutable_fact_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION protect_creation_package() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'published creation packages cannot be deleted';
          END IF;
          IF ROW(
            NEW.id, NEW.organization_id, NEW.package_key, NEW.source_project_id,
            NEW.source_workflow_run_id, NEW.source_node_run_id,
            NEW.context_snapshot_id, NEW.source_prompt_snapshot_id, NEW.package_type,
            NEW.status, NEW.target_rules_json, NEW.content_hash, NEW.created_at, NEW.created_by
          ) IS DISTINCT FROM ROW(
            OLD.id, OLD.organization_id, OLD.package_key, OLD.source_project_id,
            OLD.source_workflow_run_id, OLD.source_node_run_id,
            OLD.context_snapshot_id, OLD.source_prompt_snapshot_id, OLD.package_type,
            OLD.status, OLD.target_rules_json, OLD.content_hash, OLD.created_at, OLD.created_by
          ) THEN
            RAISE EXCEPTION 'published creation package content is immutable';
          END IF;
          IF OLD.source_stale_at IS NOT NULL
             AND NEW.source_stale_at IS DISTINCT FROM OLD.source_stale_at THEN
            RAISE EXCEPTION 'creation package stale marker is immutable once set';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_creation_packages_immutable
        BEFORE UPDATE OR DELETE ON creation_packages
        FOR EACH ROW EXECUTE FUNCTION protect_creation_package();

        CREATE FUNCTION protect_creation_immutable_fact() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'published creation facts are immutable';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_creation_package_items_immutable
        BEFORE UPDATE OR DELETE ON creation_package_items
        FOR EACH ROW EXECUTE FUNCTION protect_creation_immutable_fact();
        CREATE TRIGGER trg_creation_prompt_versions_immutable
        BEFORE UPDATE OR DELETE ON creation_prompt_versions
        FOR EACH ROW EXECUTE FUNCTION protect_creation_immutable_fact();
        CREATE TRIGGER trg_generation_results_immutable
        BEFORE UPDATE OR DELETE ON generation_results
        FOR EACH ROW EXECUTE FUNCTION protect_creation_immutable_fact();
        CREATE TRIGGER trg_adoptions_immutable
        BEFORE UPDATE OR DELETE ON adoptions
        FOR EACH ROW EXECUTE FUNCTION protect_creation_immutable_fact();
        """
    )


def _drop_immutable_fact_triggers() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_adoptions_immutable ON adoptions;
        DROP TRIGGER IF EXISTS trg_generation_results_immutable ON generation_results;
        DROP TRIGGER IF EXISTS trg_creation_prompt_versions_immutable
          ON creation_prompt_versions;
        DROP TRIGGER IF EXISTS trg_creation_package_items_immutable
          ON creation_package_items;
        DROP TRIGGER IF EXISTS trg_creation_packages_immutable ON creation_packages;
        DROP FUNCTION IF EXISTS protect_creation_package();
        DROP FUNCTION IF EXISTS protect_creation_immutable_fact();
        """
    )
