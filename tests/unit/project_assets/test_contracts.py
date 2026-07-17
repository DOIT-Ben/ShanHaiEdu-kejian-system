from __future__ import annotations

import pytest
from pydantic import ValidationError

from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
)


def test_slot_declaration_accepts_stable_semantic_keys_and_typed_contract() -> None:
    declaration = AssetSlotDeclaration(
        slot_key="lesson.02.video.shot.03.clip.selected",
        asset_type="video",
        cardinality=AssetCardinality.ONE,
        required=True,
        target_contract=AssetTargetContract(
            allowed_mime_types=("video/mp4",),
            require_clean_scan=True,
        ),
    )

    assert declaration.slot_key == "lesson.02.video.shot.03.clip.selected"
    assert declaration.target_contract.allowed_mime_types == ("video/mp4",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("slot_key", "Lesson 02 Video"),
        ("slot_key", ".lesson.video"),
        ("asset_type", "Video Clip"),
    ],
)
def test_slot_declaration_rejects_unstable_identifiers(field: str, value: str) -> None:
    payload = {
        "slot_key": "lesson.02.video.final",
        "asset_type": "video",
        "cardinality": "one",
        "required": False,
        "target_contract": {},
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        AssetSlotDeclaration.model_validate(payload)


def test_target_contract_rejects_duplicate_or_invalid_mime_types() -> None:
    with pytest.raises(ValidationError):
        AssetTargetContract(allowed_mime_types=("image/png", "image/png"))

    with pytest.raises(ValidationError):
        AssetTargetContract(allowed_mime_types=("not-a-mime",))
