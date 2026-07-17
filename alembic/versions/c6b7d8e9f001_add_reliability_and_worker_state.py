"""add reliability and worker state

Revision ID: c6b7d8e9f001
Revises: 3f62a6e7d901
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c6b7d8e9f001"
down_revision: str | Sequence[str] | None = "3f62a6e7d901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("generation_jobs", sa.Column("lease_owner", sa.String(length=160), nullable=True))
    op.add_column(
        "generation_jobs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_generation_jobs_attempt_count_nonnegative",
        "generation_jobs",
        "attempt_count >= 0",
    )
    op.create_index(
        "ix_generation_jobs_status_lease",
        "generation_jobs",
        ["status", "lease_expires_at"],
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "response_status BETWEEN 100 AND 599",
            name="ck_idempotency_records_response_status_range",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_idempotency_records_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint(
            "organization_id",
            "scope",
            "idempotency_key",
            name="uq_idempotency_records_organization_scope_key",
        ),
    )
    op.create_index(
        "ix_idempotency_records_expires_at",
        "idempotency_records",
        ["expires_at"],
    )

    op.create_table(
        "outbox_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'publishing', 'published')",
            name="ck_outbox_events_status_allowed",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_outbox_events_attempt_count_nonnegative"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_outbox_events_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_outbox_events"),
    )
    op.create_index(
        "ix_outbox_events_dispatch",
        "outbox_events",
        ["status", "available_at", "lease_expires_at"],
    )

    op.create_table(
        "event_stream_entries",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_id", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence_no > 0", name="ck_event_stream_entries_sequence_positive"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_event_stream_entries_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_event_stream_entries_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_event_stream_entries"),
        sa.UniqueConstraint(
            "project_id",
            "sequence_no",
            name="uq_event_stream_entries_project_sequence",
        ),
    )
    op.create_index(
        "ix_event_stream_entries_resource_sequence",
        "event_stream_entries",
        ["resource_type", "resource_id", "sequence_no"],
    )
    op.create_index(
        "ix_event_stream_entries_created_at",
        "event_stream_entries",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_stream_entries_created_at", table_name="event_stream_entries")
    op.drop_index("ix_event_stream_entries_resource_sequence", table_name="event_stream_entries")
    op.drop_table("event_stream_entries")
    op.drop_index("ix_outbox_events_dispatch", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("ix_idempotency_records_expires_at", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("ix_generation_jobs_status_lease", table_name="generation_jobs")
    op.drop_constraint(
        "ck_generation_jobs_attempt_count_nonnegative",
        "generation_jobs",
        type_="check",
    )
    op.drop_column("generation_jobs", "lease_expires_at")
    op.drop_column("generation_jobs", "lease_owner")
    op.drop_column("generation_jobs", "attempt_count")
