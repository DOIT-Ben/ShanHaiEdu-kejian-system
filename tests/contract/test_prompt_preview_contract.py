from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | {key for item in value.values() for key in _keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _keys(item)}
    return set()


def test_prompt_preview_contract_exposes_only_teacher_editing_fields() -> None:
    contract = yaml.safe_load(
        (ROOT / "contracts/api-surface.openapi.yaml").read_text(encoding="utf-8")
    )
    data = contract["components"]["schemas"]["PromptPreviewEnvelope"]["properties"]["data"]

    assert set(data["properties"]) == {
        "prompt_snapshot_id",
        "content_hash",
        "editable_prompt",
        "edit_policy",
    }
    assert set(data["required"]) == set(data["properties"])
    assert data["additionalProperties"] is False

    forbidden = {
        "schema",
        "output_schema",
        "locked_layers",
        "context_summary",
        "source",
        "internal_prompt",
    }
    assert forbidden.isdisjoint(_keys(data))
