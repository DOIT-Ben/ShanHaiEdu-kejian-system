from __future__ import annotations

import pytest
from pydantic import ValidationError

from apps.api.ids import new_uuid7
from apps.api.projects.schemas import CreateProjectRequest


def test_create_project_defaults_to_assisted_primary_math_workflow() -> None:
    request = CreateProjectRequest(title="Fractions", knowledge_point="Understanding one half")

    assert request.automation_mode == "assisted"
    assert request.grade is None


def test_create_project_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CreateProjectRequest(
            title="Fractions",
            knowledge_point="Understanding one half",
            provider="browser-direct",
        )


def test_business_ids_are_uuid7() -> None:
    assert new_uuid7().version == 7
