"""Constrain ArtifactRelation impact scopes to the approved shapes."""

from alembic import op

revision = "f2a7b9c1d304"
down_revision = "e6b9a2c4d801"
branch_labels = None
depends_on = None


_IMPACT_SCOPE_FUNCTION = """
CREATE OR REPLACE FUNCTION shanhai_is_canonical_impact_scope(value jsonb)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
STRICT
SET search_path = pg_catalog
AS $$
DECLARE
    key text;
    previous_key text;
    entry jsonb;
BEGIN
    IF value = '{"mode": "all"}'::jsonb THEN
        RETURN TRUE;
    END IF;
    IF jsonb_typeof(value) <> 'object'
       OR (value - 'keys') <> '{"mode": "keyed", "selector": "lesson_key"}'::jsonb
       OR jsonb_typeof(value->'keys') <> 'array'
       OR jsonb_array_length(value->'keys') = 0 THEN
        RETURN FALSE;
    END IF;
    FOR entry IN SELECT item FROM jsonb_array_elements(value->'keys') AS items(item) LOOP
        IF jsonb_typeof(entry) <> 'string' THEN
            RETURN FALSE;
        END IF;
        key := entry #>> '{}';
        IF btrim(key) = '' THEN
            RETURN FALSE;
        END IF;
        IF previous_key IS NOT NULL AND key COLLATE "C" <= previous_key COLLATE "C" THEN
            RETURN FALSE;
        END IF;
        previous_key := key;
    END LOOP;
    RETURN TRUE;
END;
$$;
"""

_IMPACT_SCOPE_CHECK = "shanhai_is_canonical_impact_scope(impact_scope_json)"


def upgrade() -> None:
    op.execute(_IMPACT_SCOPE_FUNCTION)
    op.create_check_constraint(
        "ck_artifact_relations_impact_scope_allowed",
        "artifact_relations",
        _IMPACT_SCOPE_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_artifact_relations_impact_scope_allowed",
        "artifact_relations",
        type_="check",
    )
    op.execute("DROP FUNCTION shanhai_is_canonical_impact_scope(jsonb)")
