"""Add published content and project workflow runtime.

Revision ID: a1b2c3d4e501
Revises: f4c8d2e6a103
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e501"
down_revision: str | Sequence[str] | None = "f4c8d2e6a103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYSTEM_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000002")
CONTENT_PACKAGE_ID = UUID("01970000-0000-7000-8000-000000000001")
CONTENT_PACKAGE_VERSION_ID = UUID("01970000-0000-7000-8000-000000000002")
CONTENT_RELEASE_ID = UUID("01970000-0000-7000-8000-000000000003")
CONTENT_DEFINITION_VERSION_ID = UUID("01970000-0000-7000-8000-000000000004")
WORKFLOW_DEFINITION_ID = UUID("01970000-0000-7000-8000-000000000005")
WORKFLOW_DEFINITION_VERSION_ID = UUID("01970000-0000-7000-8000-000000000006")
CONTENT_RELEASE_ITEM_ID = UUID("01970000-0000-7000-8000-000000000007")


def upgrade() -> None:
    content_packages = _create_content_packages()
    content_package_versions = _create_content_package_versions()
    content_releases = _create_content_releases()
    content_release_items = _create_content_release_items()
    content_definition_versions = _create_content_definition_versions()
    workflow_definitions = _create_workflow_definitions()
    workflow_definition_versions = _create_workflow_definition_versions()
    _seed_builtin_runtime(
        content_packages,
        content_package_versions,
        content_releases,
        content_release_items,
        content_definition_versions,
        workflow_definitions,
        workflow_definition_versions,
    )
    _pin_projects_to_builtin_runtime()
    _create_workflow_runs()
    _create_branch_runs()
    _create_node_runs()
    _create_node_input_snapshots()
    _create_immutability_triggers()


def downgrade() -> None:
    _drop_immutability_triggers()
    op.drop_index("uq_node_input_snapshots_node_input", table_name="node_input_snapshots")
    op.drop_table("node_input_snapshots")
    op.drop_index("uq_node_runs_project_active", table_name="node_runs")
    op.drop_index("uq_node_runs_branch_active", table_name="node_runs")
    op.drop_index("uq_node_runs_branch_node_run", table_name="node_runs")
    op.drop_table("node_runs")
    op.drop_index("uq_branch_runs_workflow_lesson_branch", table_name="branch_runs")
    op.drop_table("branch_runs")
    op.drop_index("uq_workflow_runs_project_active", table_name="workflow_runs")
    op.drop_index("uq_workflow_runs_project_run", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_constraint(
        "fk_projects_workflow_definition_version",
        "projects",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_projects_content_release_id_content_releases",
        "projects",
        type_="foreignkey",
    )
    op.drop_column("projects", "workflow_definition_version_id")
    op.drop_column("projects", "content_release_id")
    op.drop_index(
        "uq_workflow_definition_versions_checksum",
        table_name="workflow_definition_versions",
    )
    op.drop_index(
        "uq_workflow_definition_versions_definition_version",
        table_name="workflow_definition_versions",
    )
    op.drop_table("workflow_definition_versions")
    op.drop_index("uq_workflow_definitions_workflow_key", table_name="workflow_definitions")
    op.drop_table("workflow_definitions")
    op.drop_index(
        "uq_content_definition_versions_package_key",
        table_name="content_definition_versions",
    )
    op.drop_table("content_definition_versions")
    op.drop_index(
        "uq_content_release_items_release_mount",
        table_name="content_release_items",
    )
    op.drop_table("content_release_items")
    op.drop_index("uq_content_releases_release_key", table_name="content_releases")
    op.drop_table("content_releases")
    op.drop_index(
        "uq_content_package_versions_checksum",
        table_name="content_package_versions",
    )
    op.drop_index(
        "uq_content_package_versions_package_semver",
        table_name="content_package_versions",
    )
    op.drop_table("content_package_versions")
    op.drop_index("uq_content_packages_package_key", table_name="content_packages")
    op.drop_table("content_packages")


def _create_content_packages() -> sa.Table:
    table = op.create_table(
        "content_packages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_key", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("package_type", sa.String(length=80), nullable=False),
        sa.Column("owner_scope", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_content_packages_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_packages"),
    )
    op.create_index(
        "uq_content_packages_package_key",
        "content_packages",
        ["package_key"],
        unique=True,
    )
    return table


def _create_content_package_versions() -> sa.Table:
    table = op.create_table(
        "content_package_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_package_id", sa.Uuid(), nullable=False),
        sa.Column("semantic_version", sa.String(length=80), nullable=False),
        sa.Column("runtime_constraint", sa.String(length=120), nullable=False),
        sa.Column("manifest_json", postgresql.JSONB(), nullable=False),
        sa.Column("archive_asset_version_id", sa.Uuid(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'validated', 'published')",
            name="ck_content_package_versions_status_allowed",
        ),
        sa.CheckConstraint(
            "status <> 'published' OR (validated_at IS NOT NULL AND published_at IS NOT NULL)",
            name="ck_content_package_versions_publication_complete",
        ),
        sa.CheckConstraint(
            "checksum ~ '^[0-9a-f]{64}$'",
            name="ck_content_package_versions_checksum_format",
        ),
        sa.ForeignKeyConstraint(
            ["content_package_id"],
            ["content_packages.id"],
            name="fk_content_package_versions_content_package_id_content_packages",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["archive_asset_version_id"],
            ["file_asset_versions.id"],
            name="fk_content_package_versions_archive_asset_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_package_versions"),
    )
    op.create_index(
        "uq_content_package_versions_package_semver",
        "content_package_versions",
        ["content_package_id", "semantic_version"],
        unique=True,
    )
    op.create_index(
        "uq_content_package_versions_checksum",
        "content_package_versions",
        ["checksum"],
        unique=True,
    )
    return table


def _create_content_releases() -> sa.Table:
    table = op.create_table(
        "content_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("release_key", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'disabled')",
            name="ck_content_releases_status_allowed",
        ),
        sa.CheckConstraint(
            "status <> 'published' OR (published_at IS NOT NULL AND published_by IS NOT NULL)",
            name="ck_content_releases_publication_complete",
        ),
        sa.ForeignKeyConstraint(
            ["published_by"],
            ["principals.id"],
            name="fk_content_releases_published_by_principals",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_releases"),
    )
    op.create_index(
        "uq_content_releases_release_key",
        "content_releases",
        ["release_key"],
        unique=True,
    )
    return table


def _create_content_release_items() -> sa.Table:
    table = op.create_table(
        "content_release_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_release_id", sa.Uuid(), nullable=False),
        sa.Column("content_package_version_id", sa.Uuid(), nullable=False),
        sa.Column("mount_key", sa.String(length=160), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "priority >= 0",
            name="ck_content_release_items_priority_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["content_release_id"],
            ["content_releases.id"],
            name="fk_content_release_items_content_release_id_content_releases",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["content_package_version_id"],
            ["content_package_versions.id"],
            name="fk_content_release_items_package_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_release_items"),
    )
    op.create_index(
        "uq_content_release_items_release_mount",
        "content_release_items",
        ["content_release_id", "mount_key"],
        unique=True,
    )
    return table


def _create_content_definition_versions() -> sa.Table:
    table = op.create_table(
        "content_definition_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("definition_key", sa.String(length=160), nullable=False),
        sa.Column("content_package_version_id", sa.Uuid(), nullable=False),
        sa.Column("schema_json", postgresql.JSONB(), nullable=False),
        sa.Column("ui_schema_json", postgresql.JSONB(), nullable=False),
        sa.Column("export_mapping_json", postgresql.JSONB(), nullable=False),
        sa.Column("validation_rules_json", postgresql.JSONB(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "checksum ~ '^[0-9a-f]{64}$'",
            name="ck_content_definition_versions_checksum_format",
        ),
        sa.ForeignKeyConstraint(
            ["content_package_version_id"],
            ["content_package_versions.id"],
            name="fk_content_def_versions_package_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_definition_versions"),
    )
    op.create_index(
        "uq_content_definition_versions_package_key",
        "content_definition_versions",
        ["content_package_version_id", "definition_key"],
        unique=True,
    )
    return table


def _create_workflow_definitions() -> sa.Table:
    table = op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_key", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_workflow_definitions_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_definitions"),
    )
    op.create_index(
        "uq_workflow_definitions_workflow_key",
        "workflow_definitions",
        ["workflow_key"],
        unique=True,
    )
    return table


def _create_workflow_definition_versions() -> sa.Table:
    table = op.create_table(
        "workflow_definition_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("graph_json", postgresql.JSONB(), nullable=False),
        sa.Column("input_contract_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "version_no > 0",
            name="ck_workflow_definition_versions_version_positive",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'validated', 'published')",
            name="ck_workflow_definition_versions_status_allowed",
        ),
        sa.CheckConstraint(
            "status <> 'published' OR published_at IS NOT NULL",
            name="ck_workflow_definition_versions_publication_complete",
        ),
        sa.CheckConstraint(
            "checksum ~ '^[0-9a-f]{64}$'",
            name="ck_workflow_definition_versions_checksum_format",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_definition_id"],
            ["workflow_definitions.id"],
            name="fk_workflow_def_versions_definition",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_definition_versions"),
    )
    op.create_index(
        "uq_workflow_definition_versions_definition_version",
        "workflow_definition_versions",
        ["workflow_definition_id", "version_no"],
        unique=True,
    )
    op.create_index(
        "uq_workflow_definition_versions_checksum",
        "workflow_definition_versions",
        ["checksum"],
        unique=True,
    )
    return table


def _seed_builtin_runtime(
    content_packages: sa.Table,
    content_package_versions: sa.Table,
    content_releases: sa.Table,
    content_release_items: sa.Table,
    content_definition_versions: sa.Table,
    workflow_definitions: sa.Table,
    workflow_definition_versions: sa.Table,
) -> None:
    published_at = datetime(2026, 7, 17, tzinfo=UTC)
    op.bulk_insert(
        content_packages,
        [
            {
                "id": CONTENT_PACKAGE_ID,
                "package_key": "builtin.primary-math.core",
                "name": "Built-in primary math core",
                "package_type": "builtin",
                "owner_scope": "platform",
                "status": "active",
            }
        ],
    )
    op.bulk_insert(
        content_package_versions,
        [
            {
                "id": CONTENT_PACKAGE_VERSION_ID,
                "content_package_id": CONTENT_PACKAGE_ID,
                "semantic_version": "1.0.0",
                "runtime_constraint": ">=0.1.0",
                "manifest_json": {
                    "package_key": "builtin.primary-math.core",
                    "definitions": ["lesson_plan"],
                },
                "archive_asset_version_id": None,
                "checksum": "1" * 64,
                "status": "published",
                "validated_at": published_at,
                "published_at": published_at,
            }
        ],
    )
    op.bulk_insert(
        content_releases,
        [
            {
                "id": CONTENT_RELEASE_ID,
                "release_key": "builtin-primary-math",
                "name": "Built-in primary math release",
                "status": "published",
                "published_at": published_at,
                "published_by": SYSTEM_PRINCIPAL_ID,
                "notes": "Deterministic initial runtime release.",
            }
        ],
    )
    op.bulk_insert(
        content_release_items,
        [
            {
                "id": CONTENT_RELEASE_ITEM_ID,
                "content_release_id": CONTENT_RELEASE_ID,
                "content_package_version_id": CONTENT_PACKAGE_VERSION_ID,
                "mount_key": "primary_math",
                "priority": 100,
            }
        ],
    )
    op.bulk_insert(
        content_definition_versions,
        [
            {
                "id": CONTENT_DEFINITION_VERSION_ID,
                "definition_key": "lesson_plan",
                "content_package_version_id": CONTENT_PACKAGE_VERSION_ID,
                "schema_json": {"type": "object", "additionalProperties": True},
                "ui_schema_json": {},
                "export_mapping_json": {},
                "validation_rules_json": {},
                "checksum": "2" * 64,
            }
        ],
    )
    op.bulk_insert(
        workflow_definitions,
        [
            {
                "id": WORKFLOW_DEFINITION_ID,
                "workflow_key": "primary_math.core",
                "name": "Primary math core workflow",
                "domain": "primary_math",
                "status": "active",
            }
        ],
    )
    op.bulk_insert(
        workflow_definition_versions,
        [
            {
                "id": WORKFLOW_DEFINITION_VERSION_ID,
                "workflow_definition_id": WORKFLOW_DEFINITION_ID,
                "version_no": 1,
                "graph_json": {
                    "nodes": [
                        {
                            "node_key": "prepare",
                            "branch_key": None,
                            "dependencies": [],
                            "input_contract_refs": [],
                            "output_contract_refs": ["content:lesson_plan"],
                        }
                    ]
                },
                "input_contract_json": {
                    "available_refs": ["content:lesson_plan"],
                },
                "status": "published",
                "checksum": "3" * 64,
                "published_at": published_at,
            }
        ],
    )


def _pin_projects_to_builtin_runtime() -> None:
    op.add_column("projects", sa.Column("content_release_id", sa.Uuid(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("workflow_definition_version_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_content_release_id_content_releases",
        "projects",
        "content_releases",
        ["content_release_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_projects_workflow_definition_version",
        "projects",
        "workflow_definition_versions",
        ["workflow_definition_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        sa.text(
            "UPDATE projects SET content_release_id = :release_id, "
            "workflow_definition_version_id = :workflow_version_id"
        ).bindparams(
            release_id=CONTENT_RELEASE_ID,
            workflow_version_id=WORKFLOW_DEFINITION_VERSION_ID,
        )
    )
    op.alter_column("projects", "content_release_id", nullable=False)
    op.alter_column("projects", "workflow_definition_version_id", nullable=False)


def _mutable_audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _audit_constraints(table_name: str) -> list[sa.ForeignKeyConstraint | sa.CheckConstraint]:
    return [
        sa.CheckConstraint("lock_version >= 1", name=f"ck_{table_name}_lock_version_positive"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["principals.id"],
            name=f"fk_{table_name}_created_by_principals",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["principals.id"],
            name=f"fk_{table_name}_updated_by_principals",
            ondelete="RESTRICT",
        ),
    ]


def _create_workflow_runs() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("content_release_id", sa.Uuid(), nullable=False),
        sa.Column("automation_policy_snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("run_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_event_seq", sa.Integer(), nullable=False),
        *_mutable_audit_columns(),
        sa.CheckConstraint("run_no > 0", name="ck_workflow_runs_run_positive"),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'failed', 'cancelled')",
            name="ck_workflow_runs_status_allowed",
        ),
        sa.CheckConstraint(
            "current_event_seq >= 0",
            name="ck_workflow_runs_event_seq_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_workflow_runs_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_workflow_runs_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_definition_version_id"],
            ["workflow_definition_versions.id"],
            name="fk_workflow_runs_definition_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["content_release_id"],
            ["content_releases.id"],
            name="fk_workflow_runs_content_release_id_content_releases",
            ondelete="RESTRICT",
        ),
        *_audit_constraints("workflow_runs"),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_runs"),
    )
    op.create_index(
        "uq_workflow_runs_project_run",
        "workflow_runs",
        ["project_id", "run_no"],
        unique=True,
    )
    op.create_index(
        "uq_workflow_runs_project_active",
        "workflow_runs",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('active', 'paused') AND deleted_at IS NULL"),
    )


def _create_branch_runs() -> None:
    op.create_table(
        "branch_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_unit_id", sa.Uuid(), nullable=False),
        sa.Column("branch_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_mutable_audit_columns(),
        sa.CheckConstraint(
            "status IN ('disabled', 'active', 'paused', 'completed', 'failed', 'cancelled')",
            name="ck_branch_runs_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_runs.id"],
            name="fk_branch_runs_workflow_run_id_workflow_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_unit_id"],
            ["lesson_units.id"],
            name="fk_branch_runs_lesson_unit_id_lesson_units",
            ondelete="RESTRICT",
        ),
        *_audit_constraints("branch_runs"),
        sa.PrimaryKeyConstraint("id", name="pk_branch_runs"),
    )
    op.create_index(
        "uq_branch_runs_workflow_lesson_branch",
        "branch_runs",
        ["workflow_run_id", "lesson_unit_id", "branch_key"],
        unique=True,
    )


def _create_node_runs() -> None:
    statuses = ", ".join(
        f"'{status}'"
        for status in (
            "disabled",
            "not_ready",
            "ready",
            "draft",
            "queued",
            "running",
            "review_required",
            "approved",
            "partially_completed",
            "failed",
            "paused",
            "cancel_requested",
            "cancelled",
            "stale",
            "skipped",
        )
    )
    op.create_table(
        "node_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("branch_run_id", sa.Uuid(), nullable=True),
        sa.Column("node_key", sa.String(length=160), nullable=False),
        sa.Column("run_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column("automation_policy_snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("active_artifact_version_id", sa.Uuid(), nullable=True),
        sa.Column("stale_reason_json", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=160), nullable=True),
        *_mutable_audit_columns(),
        sa.CheckConstraint("run_no > 0", name="ck_node_runs_run_positive"),
        sa.CheckConstraint(f"status IN ({statuses})", name="ck_node_runs_status_allowed"),
        sa.CheckConstraint(
            "trigger_type IN ('manual', 'policy', 'retry', 'system')",
            name="ck_node_runs_trigger_type_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_node_runs_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_runs.id"],
            name="fk_node_runs_workflow_run_id_workflow_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_run_id"],
            ["branch_runs.id"],
            name="fk_node_runs_branch_run_id_branch_runs",
            ondelete="RESTRICT",
        ),
        *_audit_constraints("node_runs"),
        sa.PrimaryKeyConstraint("id", name="pk_node_runs"),
    )
    op.create_index(
        "uq_node_runs_branch_node_run",
        "node_runs",
        ["branch_run_id", "node_key", "run_no"],
        unique=True,
    )
    op.create_index(
        "uq_node_runs_branch_active",
        "node_runs",
        ["branch_run_id", "node_key"],
        unique=True,
        postgresql_where=sa.text(
            "branch_run_id IS NOT NULL AND "
            "status IN ('queued', 'running', 'cancel_requested') AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "uq_node_runs_project_active",
        "node_runs",
        ["workflow_run_id", "node_key"],
        unique=True,
        postgresql_where=sa.text(
            "branch_run_id IS NULL AND "
            "status IN ('queued', 'running', 'cancel_requested') AND deleted_at IS NULL"
        ),
    )


def _create_node_input_snapshots() -> None:
    op.create_table(
        "node_input_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("node_run_id", sa.Uuid(), nullable=False),
        sa.Column("input_key", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_node_input_snapshots_content_hash_format",
        ),
        sa.ForeignKeyConstraint(
            ["node_run_id"],
            ["node_runs.id"],
            name="fk_node_input_snapshots_node_run_id_node_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["principals.id"],
            name="fk_node_input_snapshots_created_by_principals",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_node_input_snapshots"),
    )
    op.create_index(
        "uq_node_input_snapshots_node_input",
        "node_input_snapshots",
        ["node_run_id", "input_key"],
        unique=True,
    )


def _create_immutability_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_published_row_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'published' THEN
                RAISE EXCEPTION 'published runtime versions are immutable'
                    USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_content_package_version_immutable
        BEFORE UPDATE OR DELETE ON content_package_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_published_row_mutation();
        CREATE TRIGGER trg_content_release_immutable
        BEFORE UPDATE OR DELETE ON content_releases
        FOR EACH ROW EXECUTE FUNCTION prevent_published_row_mutation();
        CREATE TRIGGER trg_workflow_definition_version_immutable
        BEFORE UPDATE OR DELETE ON workflow_definition_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_published_row_mutation();

        CREATE FUNCTION prevent_published_release_item_mutation()
        RETURNS trigger AS $$
        DECLARE release_id uuid;
        BEGIN
            release_id := CASE WHEN TG_OP = 'DELETE'
                THEN OLD.content_release_id ELSE NEW.content_release_id END;
            IF EXISTS (SELECT 1 FROM content_releases
                       WHERE id = release_id AND status = 'published') THEN
                RAISE EXCEPTION 'published content release items are immutable'
                    USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_content_release_item_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON content_release_items
        FOR EACH ROW EXECUTE FUNCTION prevent_published_release_item_mutation();

        CREATE FUNCTION prevent_published_definition_mutation()
        RETURNS trigger AS $$
        DECLARE package_version_id uuid;
        BEGIN
            package_version_id := CASE WHEN TG_OP = 'DELETE'
                THEN OLD.content_package_version_id ELSE NEW.content_package_version_id END;
            IF EXISTS (SELECT 1 FROM content_package_versions
                       WHERE id = package_version_id AND status = 'published') THEN
                RAISE EXCEPTION 'published content definitions are immutable'
                    USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_content_definition_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON content_definition_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_published_definition_mutation();

        CREATE FUNCTION prevent_node_input_snapshot_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'node input snapshots are immutable'
                USING ERRCODE = '23514';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_node_input_snapshot_immutable
        BEFORE UPDATE OR DELETE ON node_input_snapshots
        FOR EACH ROW EXECUTE FUNCTION prevent_node_input_snapshot_mutation();
        """
    )


def _drop_immutability_triggers() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_node_input_snapshot_immutable ON node_input_snapshots")
    op.execute("DROP FUNCTION IF EXISTS prevent_node_input_snapshot_mutation()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_content_definition_immutable ON content_definition_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_published_definition_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_content_release_item_immutable ON content_release_items")
    op.execute("DROP FUNCTION IF EXISTS prevent_published_release_item_mutation()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workflow_definition_version_immutable "
        "ON workflow_definition_versions"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_content_release_immutable ON content_releases")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_content_package_version_immutable ON content_package_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_published_row_mutation()")
