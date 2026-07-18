"""add creation batch ownership

Revision ID: e4f6a8c0b702
Revises: d2e5f8a1c604
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4f6a8c0b702"
down_revision: str | Sequence[str] | None = "d2e5f8a1c604"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("creation_batches", sa.Column("owner_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_creation_batches_owner_user_id_users",
        "creation_batches",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        UPDATE creation_batches AS batches
        SET owner_user_id = principals.user_id
        FROM principals
        WHERE batches.created_by = principals.id
          AND principals.user_id IS NOT NULL
        """
    )
    op.create_check_constraint(
        "ck_creation_batches_standalone_owner_required",
        "creation_batches",
        "source_kind <> 'standalone' OR owner_user_id IS NOT NULL",
    )
    op.create_index(
        "ix_creation_batches_organization_owner_created",
        "creation_batches",
        ["organization_id", "owner_user_id", "created_at"],
    )
    op.execute(
        """
        CREATE FUNCTION validate_creation_batch_owner_scope() RETURNS trigger AS $$
        BEGIN
          IF (TG_OP = 'INSERT' OR NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id)
             AND NEW.owner_user_id IS NOT NULL
             AND NOT EXISTS (
               SELECT 1 FROM organization_members
               WHERE organization_id = NEW.organization_id
                 AND user_id = NEW.owner_user_id
                 AND status = 'active'
             ) THEN
            RAISE EXCEPTION 'creation batch owner is outside the organization';
          END IF;
          IF TG_OP = 'UPDATE'
             AND NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id THEN
            RAISE EXCEPTION 'creation batch owner is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_creation_batch_owner_scope
        BEFORE INSERT OR UPDATE ON creation_batches
        FOR EACH ROW EXECUTE FUNCTION validate_creation_batch_owner_scope();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_creation_batch_owner_scope ON creation_batches;
        DROP FUNCTION IF EXISTS validate_creation_batch_owner_scope();
        """
    )
    op.drop_index(
        "ix_creation_batches_organization_owner_created",
        table_name="creation_batches",
    )
    op.drop_constraint(
        "ck_creation_batches_standalone_owner_required",
        "creation_batches",
        type_="check",
    )
    op.drop_constraint(
        "fk_creation_batches_owner_user_id_users",
        "creation_batches",
        type_="foreignkey",
    )
    op.drop_column("creation_batches", "owner_user_id")
