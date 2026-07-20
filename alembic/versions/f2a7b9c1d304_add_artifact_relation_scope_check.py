"""Constrain ArtifactRelation impact scopes to the approved shapes."""

from alembic import op

revision = "f2a7b9c1d304"
down_revision = "e6b9a2c4d801"
branch_labels = None
depends_on = None

_IMPACT_SCOPE_CHECK = """
(
    impact_scope_json = '{\"mode\": \"all\"}'::jsonb
    OR (
        jsonb_typeof(impact_scope_json) = 'object'
        AND (impact_scope_json - 'keys') = '{"mode": "keyed", "selector": "lesson_key"}'::jsonb
        AND jsonb_typeof(impact_scope_json->'keys') = 'array'
        AND jsonb_array_length(impact_scope_json->'keys') > 0
    )
)
"""


def upgrade() -> None:
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
