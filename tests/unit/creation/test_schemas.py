from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.api.creation.schemas import (
    LegacyGenerateCreationBatchRequest,
    SavePromptVersionRequest,
)


def test_creation_requests_reject_duplicate_uuid_references() -> None:
    repeated = uuid4()

    with pytest.raises(ValidationError):
        SavePromptVersionRequest(
            business_prompt="Draw a classroom example.",
            reference_asset_version_ids=[repeated, repeated],
            output_spec={"mime_type": "image/png"},
            generation_profile="balanced",
        )

    with pytest.raises(ValidationError):
        LegacyGenerateCreationBatchRequest(item_ids=[repeated, repeated])
