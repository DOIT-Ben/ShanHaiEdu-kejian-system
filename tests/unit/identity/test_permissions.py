from __future__ import annotations

import pytest

from apps.api.identity.context import ProjectAction, ProjectRole
from apps.api.identity.permissions import is_project_action_allowed


@pytest.mark.parametrize(
    ("role", "allowed_actions"),
    [
        (
            ProjectRole.OWNER,
            {
                ProjectAction.VIEW,
                ProjectAction.EDIT,
                ProjectAction.GENERATE,
                ProjectAction.REVIEW,
                ProjectAction.MANAGE_MEMBERS,
                ProjectAction.ARCHIVE,
            },
        ),
        (
            ProjectRole.EDITOR,
            {ProjectAction.VIEW, ProjectAction.EDIT, ProjectAction.GENERATE},
        ),
        (
            ProjectRole.REVIEWER,
            {ProjectAction.VIEW, ProjectAction.REVIEW},
        ),
        (ProjectRole.VIEWER, {ProjectAction.VIEW}),
    ],
)
def test_project_role_permission_matrix(
    role: ProjectRole,
    allowed_actions: set[ProjectAction],
) -> None:
    for action in ProjectAction:
        assert is_project_action_allowed(role, action) is (action in allowed_actions)
